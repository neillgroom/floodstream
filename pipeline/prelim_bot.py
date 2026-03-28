"""
FloodStream Prelim Bot — conversational guided input for Preliminary Reports.

Simple flow:
- /defaults sets field values that carry forward to every prelim
- /prelim asks only the questions that DON'T have a default
- Any field with a default is pre-filled and skipped
- inspection_date and contact_date auto-set to today
"""

import asyncio
import json
import logging
import os
import re
import sys
from datetime import datetime
from dataclasses import asdict

log = logging.getLogger("floodstream-bot")

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

sys.path.insert(0, os.path.dirname(__file__))

from nol_parser import parse_nol, NOLData
from prelim_schema import (
    PrelimData, PRELIM_QUESTIONS, CAUSE_CODES, ALWAYS_ASK,
    BUILDING_TYPES, OCCUPANCY_TYPES, FOUNDATION_TYPES,
)
from prelim_xml_builder import build_prelim_xml
import dropbox_api

# --- Load config ---
def _load_env():
    env = {}
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env

_env = _load_env()
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", _env.get("TELEGRAM_BOT_TOKEN", ""))

# Conversation states
ASKING_QUESTIONS, CONFIRM, COLLECTING_PHOTOS = range(3)

# Standard NFIP photo sequence
PHOTO_SEQUENCE = [
    "Front of Risk", "Address", "Right Side", "Left Side", "Rear",
    "Exterior Water Mark", "Interior Water Mark",
    "Interior Damage 1", "Interior Damage 2", "Interior Damage 3",
]

# In-progress sessions: {user_id: {...}}
sessions = {}

# --- Session persistence: survives bot crashes/restarts ---
SESSIONS_DIR = os.path.join(os.path.dirname(__file__), "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)


def _session_path(user_id: int) -> str:
    return os.path.join(SESSIONS_DIR, f"{user_id}.json")


def _save_session(user_id: int):
    """Save current session state to disk after every answer."""
    session = sessions.get(user_id)
    if not session:
        return
    try:
        # Serialize what we need to resume
        data = {
            "prelim": asdict(session["prelim"]),
            "question_index": session["question_index"],
            "questions": session["questions"],  # list of tuples serializes as lists
            "carrier_name": session.get("carrier_name", ""),
            "claim_number": session.get("claim_number", ""),
            "property_address": session.get("property_address", ""),
            "property_csz": session.get("property_csz", ""),
            "chat_id": session.get("chat_id"),
            "state": session.get("state", "asking"),
            "saved_at": datetime.now().isoformat(),
        }
        with open(_session_path(user_id), "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass  # Don't crash the bot over a save failure


def _delete_session_file(user_id: int):
    """Remove session file after completion or cancel."""
    try:
        path = _session_path(user_id)
        if os.path.exists(path):
            os.unlink(path)
    except OSError:
        pass


def _load_saved_sessions() -> dict[int, dict]:
    """Load all saved sessions from disk on startup. Returns {user_id: session_data}."""
    saved = {}
    if not os.path.isdir(SESSIONS_DIR):
        return saved
    for fname in os.listdir(SESSIONS_DIR):
        if not fname.endswith(".json"):
            continue
        try:
            user_id = int(fname.replace(".json", ""))
            with open(os.path.join(SESSIONS_DIR, fname)) as f:
                data = json.load(f)
            # Reconstruct PrelimData from dict
            prelim = PrelimData(**{k: v for k, v in data["prelim"].items() if hasattr(PrelimData, k)})
            # Reconstruct questions as tuples
            questions = [tuple(q) for q in data["questions"]]
            saved[user_id] = {
                "prelim": prelim,
                "nol": NOLData(),  # Can't serialize full NOL, not needed for resume
                "question_index": data["question_index"],
                "questions": questions,
                "carrier_name": data.get("carrier_name", ""),
                "claim_number": data.get("claim_number", ""),
                "property_address": data.get("property_address", ""),
                "property_csz": data.get("property_csz", ""),
                "chat_id": data.get("chat_id"),
                "state": data.get("state", "asking"),
            }
        except Exception:
            pass
    return saved


# Restore sessions on import (bot startup)
_restored = _load_saved_sessions()
sessions.update(_restored)
_RESTORED_COUNT = len(_restored)


async def resume_saved_sessions(bot):
    """After bot starts, notify users with incomplete prelims to continue."""
    for user_id, session in list(sessions.items()):
        chat_id = session.get("chat_id")
        if not chat_id:
            continue

        prelim = session["prelim"]
        questions = session["questions"]
        idx = session["question_index"]
        name = prelim.insured_name or prelim.adjuster_file_number or "?"

        if idx < len(questions):
            field_name, question, input_type, hint = questions[idx]
            prompt = f"({idx + 1}/{len(questions)}) {question}"
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"Resuming prelim for {name}\n\n{prompt}",
                )
            except Exception:
                pass

# --- Defaults: persisted to disk, applied to every prelim ---
DEFAULTS_PATH = os.path.join(os.path.dirname(__file__), "defaults.json")

# Aliases: only event-level + advance defaults — building info is ALWAYS asked
FIELD_ALIASES = {
    "rainfall": ("cause", "rainfall"),
    "river": ("cause", "river"),
    "surge": ("cause", "surge"),
    "mudflow": ("cause", "mudflow"),
    "erosion": ("cause", "erosion"),
    "no advance": ("advance_payment_building", "0.00"),
}

LINKED_DEFAULTS = {
    "no advance": {"advance_payment_building": "0.00", "advance_payment_contents": "0.00"},
}


def _load_defaults() -> dict:
    if os.path.exists(DEFAULTS_PATH):
        try:
            with open(DEFAULTS_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _save_defaults(defaults: dict):
    try:
        with open(DEFAULTS_PATH, "w") as f:
            json.dump(defaults, f, indent=2)
    except IOError:
        pass


def normalize_date_yyyymmdd(date_str: str) -> str:
    date_str = date_str.strip()
    for fmt in ["%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d", "%m/%d/%y"]:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y%m%d")
        except ValueError:
            continue
    return date_str


def validate_input(field_name: str, input_type: str, value: str, options=None) -> tuple[bool, str, str]:
    value = value.strip()
    log.info(f"[VALIDATE] {field_name} ({input_type}): '{value}'")

    if input_type == "date":
        cleaned = normalize_date_yyyymmdd(value)
        if re.match(r'^\d{8}$', cleaned):
            return True, cleaned, ""
        return False, "", "Use MM/DD/YYYY"

    elif input_type == "datetime":
        # Strict match: 2/10/2025 12:00 AM
        if re.match(r'\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s*[AaPp][Mm]?', value):
            return True, value, ""
        # Shorthand: 2/10/2025 12a, 2/10/2025 3pm, 2/10/2025 12am
        m = re.match(r'(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2})\s*([AaPp][Mm]?)\s*$', value)
        if m:
            date_part, hour, ampm = m.group(1), m.group(2), m.group(3).upper()
            if len(ampm) == 1:
                ampm = ampm + "M"  # "a" → "AM", "p" → "PM"
            normalized = f"{date_part} {hour}:00 {ampm}"
            return True, normalized, ""
        return False, "", "Use MM/DD/YYYY HH:MM AM (or just 12a, 3pm)"

    elif input_type == "number":
        try:
            cleaned = re.sub(r'[\s"\']+$', '', value)  # strip trailing ", ', whitespace
            cleaned = re.sub(r'\s*(inches|inch|in|ft|feet)\s*$', '', cleaned, flags=re.IGNORECASE)
            return True, str(float(cleaned.replace(",", ""))), ""
        except ValueError:
            return False, "", "Enter a number"

    elif input_type == "dollar":
        try:
            return True, f"{float(value.replace(',', '').replace('$', '')):.2f}", ""
        except ValueError:
            return False, "", "Enter a dollar amount"

    elif input_type == "yesno":
        if value.lower() in ("y", "yes", "true", "1"):
            return True, "YES", ""
        if value.lower() in ("n", "no", "false", "0", ""):
            return True, "NO", ""
        return False, "", "Yes or no"

    elif input_type == "choice" and options:
        for opt in options:
            if value.lower() == opt.lower():
                return True, opt, ""
        try:
            idx = int(value) - 1
            if 0 <= idx < len(options):
                return True, options[idx], ""
        except ValueError:
            pass
        for opt in options:
            if value.lower() in opt.lower():
                return True, opt, ""
        opts = "\n".join(f"  {i+1}. {o}" for i, o in enumerate(options))
        return False, "", f"Choose one:\n{opts}"

    return True, value, ""


# ===== /defaults command =====

async def cmd_defaults(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set or view defaults. Usage: /defaults dwelling, owner-occ, slab, 1 floor, no split, rainfall"""
    args = " ".join(context.args) if context.args else ""
    defaults = _load_defaults()

    if not args or args.lower() == "show":
        if not defaults:
            await update.message.reply_text(
                "No defaults set.\n\n"
                "Usage: /defaults rainfall, entered 03/15/2026 12:00 PM, receded 03/16/2026 06:00 AM\n\n"
                "Defaultable: cause, water entered/receded dates.\n"
                "Everything else is always asked."
            )
        else:
            lines = ["Current defaults:"]
            for k, v in defaults.items():
                lines.append(f"  {k}: {v}")
            lines.append("\n/defaults clear to remove all")
            await update.message.reply_text("\n".join(lines))
        return

    if args.lower() == "clear":
        _save_defaults({})
        await update.message.reply_text("Defaults cleared.")
        return

    # Parse the input — comma-separated terms
    terms = [t.strip() for t in args.split(",") if t.strip()]
    applied = []

    for term in terms:
        term_lower = term.lower().strip()

        # Check linked defaults (e.g. "no advance" sets both fields)
        if term_lower in LINKED_DEFAULTS:
            for field, val in LINKED_DEFAULTS[term_lower].items():
                defaults[field] = val
                applied.append(f"{field} = {val}")
            continue

        # Check aliases
        if term_lower in FIELD_ALIASES:
            field, val = FIELD_ALIASES[term_lower]
            defaults[field] = val
            applied.append(f"{field} = {val}")
            continue

        # Try "X floor(s)" pattern
        m = re.match(r'^(\d+)\s*floors?$', term_lower)
        if m:
            defaults["number_of_floors"] = m.group(1)
            applied.append(f"number_of_floors = {m.group(1)}")
            continue

        # Try "entered MM/DD/YYYY HH:MM AM" pattern
        m = re.match(r'^entered\s+(.+)$', term_lower)
        if m:
            defaults["water_entered_date"] = m.group(1).strip()
            applied.append(f"water_entered_date = {m.group(1).strip()}")
            continue

        m = re.match(r'^receded\s+(.+)$', term_lower)
        if m:
            defaults["water_receded_date"] = m.group(1).strip()
            applied.append(f"water_receded_date = {m.group(1).strip()}")
            continue

        # Try "field=value" explicit syntax
        if "=" in term:
            field, val = term.split("=", 1)
            field = field.strip()
            val = val.strip()
            if field in ALWAYS_ASK:
                applied.append(f"x {field} — always asked, can't default")
                continue
            if hasattr(PrelimData, field):
                defaults[field] = val
                applied.append(f"{field} = {val}")
                continue

        applied.append(f"? didn't understand: {term}")

    _save_defaults(defaults)

    msg = "Defaults updated:\n" + "\n".join(f"  {a}" for a in applied)
    msg += f"\n\nThese will pre-fill on every /prelim. Fields with defaults are skipped."
    await update.message.reply_text(msg)


# ===== /prelim command =====

async def cmd_prelim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a new prelim report. Auto-cancels any stuck session."""
    user_id = update.effective_user.id
    args = " ".join(context.args) if context.args else ""

    # Auto-cancel any stuck session from a previous prelim
    if user_id in sessions:
        old = sessions[user_id]
        old_name = old.get("prelim", PrelimData()).insured_name or "previous"
        del sessions[user_id]
        _delete_session_file(user_id)
        # Clean up temp photos
        photo_dir = os.path.join(os.path.dirname(__file__), "photo_temp", str(user_id))
        if os.path.isdir(photo_dir):
            import shutil
            shutil.rmtree(photo_dir, ignore_errors=True)
        await update.message.reply_text(f"(cancelled {old_name} prelim)")

    if not args:
        await update.message.reply_text(
            "/prelim FG151849  or  /prelim HURLEY\n\n"
            "I'll search Dropbox for the NOL and pre-fill what I can."
        )
        return ConversationHandler.END

    # Search for NOL via Dropbox API
    query = args.strip()
    nol_data = None

    if not dropbox_api.is_configured():
        await update.message.reply_text("Dropbox not configured. Entering all fields manually.")
        nol_data = NOLData()
    else:
        await update.message.reply_text(f"Searching Dropbox for {query}...")
        nol_results = _find_nol(query)

        if nol_results:
            nol_info = nol_results[0]
            await update.message.reply_text(f"Found: {nol_info['name']}\nDownloading...")

            try:
                local_path = _download_nol(nol_info["path"])
                nol_data = parse_nol(local_path, use_ai=True)

                # Show what was found and what's missing
                found = []
                missing = []
                for label, val in [
                    ("Insured", nol_data.insured_name),
                    ("Policy", nol_data.policy_number),
                    ("DOL", nol_data.date_of_loss),
                    ("Carrier", nol_data.carrier),
                    ("Bldg cov", nol_data.building_coverage),
                    ("Cont cov", nol_data.contents_coverage),
                ]:
                    if val:
                        found.append(f"  {label}: {val}")
                    else:
                        missing.append(label)

                msg = f"NOL ({nol_data.confidence:.0%})"
                if found:
                    msg += "\n" + "\n".join(found)
                if missing:
                    msg += f"\n\nMissing: {', '.join(missing)}"
                if nol_data.warnings:
                    msg += "\n" + "\n".join(f"  ! {w}" for w in nol_data.warnings[:3])

                await update.message.reply_text(msg)

                # Clean up temp file
                try:
                    os.unlink(local_path)
                    os.rmdir(os.path.dirname(local_path))
                except OSError:
                    pass
            except Exception as e:
                await update.message.reply_text(f"Download failed: {e}\nEntering manually.")
                nol_data = NOLData()
        else:
            await update.message.reply_text(f"No NOL found for '{query}'. Entering manually.")
            nol_data = NOLData()

    fg_number = query if query.upper().startswith("FG") else ""

    # Build PrelimData
    prelim = PrelimData()
    prelim.adjuster_file_number = fg_number
    prelim.insured_name = nol_data.insured_name
    prelim.insured_first_name = nol_data.insured_first_name
    prelim.policy_number = nol_data.policy_number
    prelim.date_of_loss = normalize_date_yyyymmdd(nol_data.date_of_loss) if nol_data.date_of_loss else ""
    prelim.coverage_building = nol_data.building_coverage
    prelim.coverage_contents = nol_data.contents_coverage

    # Auto-set: inspection date = today, contact date entered manually
    today = datetime.now().strftime("%Y%m%d")
    prelim.inspection_date = today
    prelim.report_date = today

    # Apply /defaults
    defaults = _load_defaults()
    for field, val in defaults.items():
        if hasattr(prelim, field) and val:
            setattr(prelim, field, val)

    # Build question list — ALWAYS_ASK fields are never skipped
    # Only defaultable fields (cause, water dates) get skipped when they have a value
    questions_to_ask = []
    for q in PRELIM_QUESTIONS:
        field_name = q[0]
        if field_name in ALWAYS_ASK:
            questions_to_ask.append(q)
        elif not getattr(prelim, field_name, ""):
            questions_to_ask.append(q)

    # Property info for photo sheet
    property_csz = ", ".join(filter(None, [
        nol_data.property_city, nol_data.property_state, nol_data.property_zip,
    ]))

    sessions[user_id] = {
        "prelim": prelim,
        "nol": nol_data,
        "question_index": 0,
        "questions": questions_to_ask,
        "carrier_name": nol_data.carrier or "",
        "claim_number": nol_data.claim_number or "",
        "property_address": nol_data.property_address or "",
        "property_csz": property_csz,
        "chat_id": update.effective_chat.id,
        "state": "asking",
    }
    _save_session(user_id)

    skipped = len(PRELIM_QUESTIONS) - len(questions_to_ask)
    if skipped > 0:
        await update.message.reply_text(
            f"{len(questions_to_ask)} questions ({skipped} from defaults)"
        )
    else:
        await update.message.reply_text(f"{len(questions_to_ask)} questions")

    await _ask_next(update, user_id, context)
    return ASKING_QUESTIONS


REPROMPT_SECONDS = 120  # Re-send question after 2 minutes of silence


async def _reprompt_callback(context: ContextTypes.DEFAULT_TYPE):
    """Re-send the last question if no answer received within timeout."""
    job_data = context.job.data
    user_id = job_data["user_id"]
    expected_idx = job_data["question_index"]

    session = sessions.get(user_id)
    if not session:
        return

    # Only re-prompt if still on the same question (no answer received)
    if session["question_index"] != expected_idx:
        return

    chat_id = job_data["chat_id"]
    prompt = job_data["prompt"]

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"(still waiting) {prompt}",
        )
    except Exception:
        pass


def _schedule_reprompt(context, user_id, chat_id, question_index, prompt):
    """Schedule a re-prompt job, cancelling any previous one for this user."""
    job_name = f"reprompt_{user_id}"

    # Cancel existing reprompt for this user
    if context.job_queue:
        current_jobs = context.job_queue.get_jobs_by_name(job_name)
        for job in current_jobs:
            job.schedule_removal()

        context.job_queue.run_once(
            _reprompt_callback,
            when=REPROMPT_SECONDS,
            data={
                "user_id": user_id,
                "chat_id": chat_id,
                "question_index": question_index,
                "prompt": prompt,
            },
            name=job_name,
        )


async def _ask_next(update, user_id, context=None):
    session = sessions.get(user_id)
    if not session:
        return

    questions = session["questions"]
    idx = session["question_index"]

    if idx >= len(questions):
        await _show_summary(update, user_id)
        return

    field_name, question, input_type, hint = questions[idx]

    prompt = f"({idx + 1}/{len(questions)}) {question}"

    if hint and input_type == "choice":
        keyboard = [[opt] for opt in hint[:6]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(prompt, reply_markup=reply_markup)
    else:
        if hint:
            prompt += f"  ({hint})"
        await update.message.reply_text(prompt, reply_markup=ReplyKeyboardRemove())

    # Schedule re-prompt in case message gets lost
    if context:
        _schedule_reprompt(
            context, user_id, update.effective_chat.id, idx, prompt
        )


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = sessions.get(user_id)
    if not session:
        log.warning(f"[PRELIM] user={user_id} sent answer but no active session")
        await update.message.reply_text("No active prelim. Start with /prelim")
        return ConversationHandler.END

    questions = session["questions"]
    idx = session["question_index"]
    if idx >= len(questions):
        log.warning(f"[PRELIM] user={user_id} question_index {idx} out of range ({len(questions)} questions)")
        return ConversationHandler.END

    field_name, question, input_type, options = questions[idx]
    answer = update.message.text.strip()
    log.info(f"[PRELIM] user={user_id} Q{idx+1}/{len(questions)} {field_name}: '{answer}'")

    # Skip
    if answer.lower() in ("skip", "-", "s"):
        session["question_index"] += 1
        await _ask_next(update, user_id, context)
        return ASKING_QUESTIONS

    # Validate
    is_valid, cleaned, error = validate_input(field_name, input_type, answer, options)
    if not is_valid:
        await update.message.reply_text(f"{error}")
        return ASKING_QUESTIONS

    setattr(session["prelim"], field_name, cleaned)
    session["question_index"] += 1
    _save_session(user_id)
    await _ask_next(update, user_id, context)
    return ASKING_QUESTIONS


async def _show_summary(update, user_id):
    session = sessions.get(user_id)
    if not session:
        return

    p = session["prelim"]
    summary = (
        f"{p.insured_name} ({p.adjuster_file_number})\n"
        f"Water: {p.water_height_external}\" ext / {p.water_height_internal}\" int\n"
        f"{p.building_type}, {p.number_of_floors}fl, {p.foundation_type}\n"
        f"{p.occupancy}\n"
        f"Elev: {p.building_elevated} | Split: {p.split_level} | Cause: {p.cause}\n"
        f"Reserves: ${p.reserves_building} / ${p.reserves_content}\n"
        f"Advance: ${p.advance_payment_building} / ${p.advance_payment_contents}\n"
        f"\n'go' to generate, # to edit"
    )
    await update.message.reply_text(summary, reply_markup=ReplyKeyboardRemove())
    return CONFIRM


async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = sessions.get(user_id)
    if not session:
        log.warning(f"[CONFIRM] user={user_id} no session")
        return ConversationHandler.END

    answer = update.message.text.strip().lower()
    log.info(f"[CONFIRM] user={user_id} input='{answer}'")

    if answer in ("generate", "gen", "go", "yes", "y", "done"):
        session["photos"] = []
        session["photo_index"] = 0
        await update.message.reply_text(
            f"Send photos. 1: {PHOTO_SEQUENCE[0]}\n'done' to finish, 'skip' for none."
        )
        return COLLECTING_PHOTOS

    try:
        q_num = int(answer) - 1
        questions = session["questions"]
        if 0 <= q_num < len(questions):
            session["question_index"] = q_num
            await _ask_next(update, user_id, context)
            return ASKING_QUESTIONS
    except ValueError:
        pass

    await update.message.reply_text(f"'go' to generate, or 1-{len(session['questions'])} to edit.")
    return CONFIRM


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = sessions.get(user_id)
    if not session:
        return ConversationHandler.END

    photo_index = session.get("photo_index", 0)
    photos = session.get("photos", [])

    photo = update.message.photo[-1]
    caption = update.message.caption or ""

    photo_dir = os.path.join(os.path.dirname(__file__), "photo_temp", str(user_id))
    os.makedirs(photo_dir, exist_ok=True)

    file = await context.bot.get_file(photo.file_id)
    photo_path = os.path.join(photo_dir, f"photo_{photo_index + 1:02d}.jpg")
    await file.download_to_drive(photo_path)

    label = caption.upper() if caption else (
        PHOTO_SEQUENCE[photo_index] if photo_index < len(PHOTO_SEQUENCE) else f"PHOTO {photo_index + 1}"
    )

    photos.append({
        "path": photo_path,
        "label": label,
        "date_taken": datetime.now().strftime("%m/%d/%Y"),
        "comment": caption,
    })
    session["photos"] = photos
    session["photo_index"] = photo_index + 1

    next_idx = photo_index + 1
    if next_idx < len(PHOTO_SEQUENCE):
        await update.message.reply_text(f"{label}. Next: {PHOTO_SEQUENCE[next_idx]} ('done' to finish)")
    else:
        await update.message.reply_text(f"{label}. More or 'done'.")
    return COLLECTING_PHOTOS


async def handle_photo_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = sessions.get(user_id)
    if not session:
        return ConversationHandler.END

    answer = update.message.text.strip().lower()
    if answer in ("done", "finish", "generate", "go"):
        return await _generate(update, context, user_id)
    if answer in ("skip", "s", "no photos"):
        return await _generate(update, context, user_id)
    await update.message.reply_text("Send photo or 'done'.")
    return COLLECTING_PHOTOS


async def _generate(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    session = sessions[user_id]
    prelim = session["prelim"]
    photos_data = session.get("photos", [])

    # Log the full prelim data for debugging
    log.info(f"[GENERATE] user={user_id} starting generation ({len(photos_data)} photos)")
    log.info(f"[GENERATE] prelim data: {json.dumps(asdict(prelim), default=str)}")

    await update.message.reply_text(f"Generating ({len(photos_data)} photos)...")

    try:
        from photo_sheet import PhotoItem
        photo_items = [
            PhotoItem(
                image_path=p["path"], label=p["label"],
                date_taken=p["date_taken"], comment=p.get("comment", ""),
            )
            for p in photos_data
        ]

        from prelim_pdf import generate_prelim_package
        out_dir = os.path.join(os.path.dirname(__file__), "output")
        result = await asyncio.to_thread(
            generate_prelim_package, prelim, photo_items, out_dir,
            carrier_name=session.get("carrier_name", ""),
            claim_number=session.get("claim_number", ""),
            property_address=session.get("property_address", ""),
            property_csz=session.get("property_csz", ""),
        )
        log.info(f"[GENERATE] user={user_id} success: {result.get('pdf_path', 'unknown')}")
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log.error(f"[GENERATE] user={user_id} FAILED:\n{tb}")
        # Write crash report to file for persistent diagnosis
        crash_dir = os.path.join(os.path.dirname(__file__), "crash_logs")
        os.makedirs(crash_dir, exist_ok=True)
        crash_file = os.path.join(crash_dir, f"crash_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        with open(crash_file, "w") as f:
            f.write(f"User: {user_id}\n")
            f.write(f"Time: {datetime.now().isoformat()}\n")
            f.write(f"Prelim: {json.dumps(asdict(prelim), default=str, indent=2)}\n")
            f.write(f"Photos: {len(photos_data)}\n")
            f.write(f"Session keys: {list(session.keys())}\n\n")
            f.write(tb)
        log.error(f"[GENERATE] crash log written to {crash_file}")
        await update.message.reply_text(f"Generation failed: {e}\nData saved, try again or contact Neill.")
        return ConversationHandler.END

    with open(result["pdf_path"], "rb") as f:
        await update.message.reply_document(
            document=f, filename=os.path.basename(result["pdf_path"]),
            caption=f"Prelim PDF ({len(photos_data)} photos)"
        )

    xml_bytes = result["xml_string"].encode("utf-8")
    await update.message.reply_document(
        document=xml_bytes, filename=os.path.basename(result["xml_path"]),
        caption="Prelim XML"
    )

    from db import push_claim
    push_claim(
        fg_number=prelim.adjuster_file_number or "UNKNOWN",
        insured_name=prelim.insured_name,
        policy_number=prelim.policy_number,
        date_of_loss=prelim.date_of_loss,
        carrier=session.get("carrier_name", ""),
        report_type="prelim",
        confidence=1.0,
        xml_data=asdict(prelim),
        xml_output=result["xml_string"],
        warnings=[],
        source="telegram",
    )
    await update.message.reply_text("Sent to dashboard.")

    photo_dir = os.path.join(os.path.dirname(__file__), "photo_temp", str(user_id))
    if os.path.isdir(photo_dir):
        import shutil
        shutil.rmtree(photo_dir, ignore_errors=True)

    del sessions[user_id]
    _delete_session_file(user_id)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in sessions:
        photo_dir = os.path.join(os.path.dirname(__file__), "photo_temp", str(user_id))
        if os.path.isdir(photo_dir):
            import shutil
            shutil.rmtree(photo_dir, ignore_errors=True)
        del sessions[user_id]
    _delete_session_file(user_id)
    await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def _find_nol(query: str) -> list[dict]:
    """Search for NOL files via Dropbox API. Returns list of {name, path, size}."""
    if dropbox_api.is_configured():
        return dropbox_api.find_nol(query)
    return []


def _download_nol(dropbox_path: str) -> str:
    """Download NOL from Dropbox to a temp file. Returns local path."""
    return dropbox_api.download_file(dropbox_path)


def get_prelim_handlers():
    return ConversationHandler(
        entry_points=[CommandHandler("prelim", cmd_prelim)],
        states={
            ASKING_QUESTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirm)],
            COLLECTING_PHOTOS: [
                MessageHandler(filters.PHOTO, handle_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_photo_text),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
