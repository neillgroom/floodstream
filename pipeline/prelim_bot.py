"""
FloodStream Prelim Bot — conversational guided input for Preliminary Reports.

The bot walks Julio through each required field step by step.
Pre-fills from NOL, prompts for inspection data, generates XML.

Uses Telegram conversation states to track where each user is in the flow.
"""

import asyncio
import os
import re
import sys
from datetime import datetime
from dataclasses import asdict

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

sys.path.insert(0, os.path.dirname(__file__))

from nol_parser import parse_nol, NOLData
from prelim_schema import (
    PrelimData, PRELIM_QUESTIONS, CAUSE_CODES,
    BUILDING_TYPES, OCCUPANCY_TYPES, FOUNDATION_TYPES,
)
from prelim_xml_builder import build_prelim_xml

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
WAITING_FOR_NOL, ASKING_QUESTIONS, CONFIRM, COLLECTING_PHOTOS = range(4)

# Standard NFIP photo sequence
PHOTO_SEQUENCE = [
    "Front of Risk",
    "Address",
    "Right Side",
    "Left Side",
    "Rear",
    "Exterior Water Mark",
    "Interior Water Mark",
    "Interior Damage 1",
    "Interior Damage 2",
    "Interior Damage 3",
]

# In-progress prelim sessions: {user_id: {prelim_data, nol_data, question_index, photos}}
sessions = {}


def normalize_date_yyyymmdd(date_str: str) -> str:
    """Convert date input to YYYYMMDD."""
    date_str = date_str.strip()
    for fmt in ["%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d", "%m/%d/%y"]:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y%m%d")
        except ValueError:
            continue
    return date_str


def validate_input(field_name: str, input_type: str, value: str, options=None) -> tuple[bool, str, str]:
    """
    Validate user input for a field.
    Returns: (is_valid, cleaned_value, error_message)
    """
    value = value.strip()

    if input_type == "date":
        # Accept various date formats
        cleaned = normalize_date_yyyymmdd(value)
        if re.match(r'^\d{8}$', cleaned):
            return True, cleaned, ""
        return False, "", f"Invalid date. Use MM/DD/YYYY (e.g. 07/31/2025)"

    elif input_type == "datetime":
        # Accept datetime with AM/PM
        if re.match(r'\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s*[AaPp][Mm]', value):
            return True, value, ""
        return False, "", f"Use format: MM/DD/YYYY HH:MM AM (e.g. 07/31/2025 12:00 PM)"

    elif input_type == "number":
        try:
            num = float(value.replace(",", ""))
            return True, str(num), ""
        except ValueError:
            return False, "", "Enter a number"

    elif input_type == "dollar":
        try:
            num = float(value.replace(",", "").replace("$", ""))
            return True, f"{num:.2f}", ""
        except ValueError:
            return False, "", "Enter a dollar amount (e.g. 10000)"

    elif input_type == "yesno":
        if value.lower() in ("y", "yes", "true", "1"):
            return True, "YES", ""
        elif value.lower() in ("n", "no", "false", "0", ""):
            return True, "NO", ""
        return False, "", "Enter yes or no"

    elif input_type == "choice":
        if options:
            # Try exact match first
            for opt in options:
                if value.lower() == opt.lower():
                    return True, opt, ""
            # Try number selection
            try:
                idx = int(value) - 1
                if 0 <= idx < len(options):
                    return True, options[idx], ""
            except ValueError:
                pass
            # Try partial match
            for opt in options:
                if value.lower() in opt.lower():
                    return True, opt, ""
            opts_display = "\n".join(f"  {i+1}. {o}" for i, o in enumerate(options))
            return False, "", f"Choose one:\n{opts_display}"

    return True, value, ""


async def cmd_prelim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a new prelim report — /prelim <FG number or NOL path>."""
    user_id = update.effective_user.id
    args = " ".join(context.args) if context.args else ""

    if not args:
        await update.message.reply_text(
            "Start a Preliminary Report\n\n"
            "Usage: /prelim FG151849\n"
            "   or: /prelim (then send the NOL file)\n\n"
            "I'll pre-fill what I can from the NOL and walk you through the rest."
        )
        return ConversationHandler.END

    # Try to find and parse the NOL
    nol_data = None
    fg_number = args.strip()

    # Search for NOL in common locations
    nol_paths = _find_nol(fg_number)
    if nol_paths:
        nol_path = nol_paths[0]
        await update.message.reply_text(f"Found NOL: {os.path.basename(nol_path)}\nParsing...")
        nol_data = parse_nol(nol_path)
        await update.message.reply_text(
            f"NOL parsed ({nol_data.confidence:.0%} confidence)\n"
            f"  Carrier: {nol_data.carrier}\n"
            f"  Insured: {nol_data.insured_name}\n"
            f"  Policy: {nol_data.policy_number}\n"
            f"  DOL: {nol_data.date_of_loss}\n"
            f"  Bldg coverage: ${nol_data.building_coverage}\n"
            f"  Cont coverage: ${nol_data.contents_coverage}"
        )
    else:
        await update.message.reply_text(
            f"No NOL found for {fg_number}. You can send the NOL file, "
            f"or I'll ask for everything manually."
        )
        nol_data = NOLData()

    # Pre-fill PrelimData from NOL
    prelim = PrelimData()
    prelim.adjuster_file_number = fg_number if fg_number.startswith("FG") else ""
    prelim.insured_name = nol_data.insured_name
    prelim.insured_first_name = nol_data.insured_first_name
    prelim.policy_number = nol_data.policy_number
    prelim.date_of_loss = normalize_date_yyyymmdd(nol_data.date_of_loss) if nol_data.date_of_loss else ""
    prelim.coverage_building = nol_data.building_coverage
    prelim.coverage_contents = nol_data.contents_coverage

    # Start session
    sessions[user_id] = {
        "prelim": prelim,
        "nol": nol_data,
        "question_index": 0,
    }

    # Ask the first question
    await _ask_next_question(update, user_id)
    return ASKING_QUESTIONS


async def _ask_next_question(update, user_id):
    """Ask the next question in the sequence."""
    session = sessions.get(user_id)
    if not session:
        return

    idx = session["question_index"]
    if idx >= len(PRELIM_QUESTIONS):
        # All questions answered — show summary
        await _show_summary(update, user_id)
        return

    field_name, question, input_type, hint = PRELIM_QUESTIONS[idx]
    prelim = session["prelim"]
    current_val = getattr(prelim, field_name, "")

    # Build the prompt
    prompt = f"({idx + 1}/{len(PRELIM_QUESTIONS)}) {question}"
    if current_val:
        prompt += f"\n[Pre-filled: {current_val} — press Enter or type 'ok' to keep]"
    if hint and input_type == "choice":
        # Show numbered options
        keyboard = [[opt] for opt in hint[:6]]  # Max 6 rows
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(prompt, reply_markup=reply_markup)
    else:
        if hint and input_type != "choice":
            prompt += f"\n({hint})"
        await update.message.reply_text(prompt, reply_markup=ReplyKeyboardRemove())


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle a response to a prelim question."""
    user_id = update.effective_user.id
    session = sessions.get(user_id)
    if not session:
        await update.message.reply_text("No active prelim session. Start with /prelim")
        return ConversationHandler.END

    idx = session["question_index"]
    if idx >= len(PRELIM_QUESTIONS):
        return ConversationHandler.END

    field_name, question, input_type, options = PRELIM_QUESTIONS[idx]
    prelim = session["prelim"]
    answer = update.message.text.strip()

    # Allow "ok" or empty to keep pre-filled value
    current_val = getattr(prelim, field_name, "")
    if answer.lower() in ("ok", "keep", "") and current_val:
        session["question_index"] += 1
        await _ask_next_question(update, user_id)
        return ASKING_QUESTIONS

    # Skip with "skip" or "-"
    if answer.lower() in ("skip", "-", "s"):
        session["question_index"] += 1
        await _ask_next_question(update, user_id)
        return ASKING_QUESTIONS

    # Validate
    is_valid, cleaned, error = validate_input(field_name, input_type, answer, options)

    if not is_valid:
        await update.message.reply_text(f"Invalid: {error}\nTry again:")
        return ASKING_QUESTIONS

    # Set the value
    setattr(prelim, field_name, cleaned)
    session["question_index"] += 1

    await _ask_next_question(update, user_id)
    return ASKING_QUESTIONS


async def _show_summary(update, user_id):
    """Show summary of all collected data and ask for confirmation."""
    session = sessions.get(user_id)
    if not session:
        return

    prelim = session["prelim"]

    summary = (
        "PRELIM REPORT SUMMARY\n"
        "=====================\n"
        f"Insured: {prelim.insured_name}\n"
        f"Policy: {prelim.policy_number}\n"
        f"DOL: {prelim.date_of_loss}\n"
        f"File #: {prelim.adjuster_file_number}\n"
        f"\n"
        f"Contact: {prelim.contact_date}\n"
        f"Inspection: {prelim.inspection_date}\n"
        f"\n"
        f"Water ext: {prelim.water_height_external}\" int: {prelim.water_height_internal}\"\n"
        f"Entered: {prelim.water_entered_date}\n"
        f"Receded: {prelim.water_receded_date}\n"
        f"\n"
        f"Building: {prelim.building_type} ({prelim.number_of_floors} floors)\n"
        f"Occupancy: {prelim.occupancy}\n"
        f"Foundation: {prelim.foundation_type}\n"
        f"Elevated: {prelim.building_elevated}\n"
        f"Cause: {prelim.cause}\n"
        f"\n"
        f"Coverage: Bldg ${prelim.coverage_building} / Cont ${prelim.coverage_contents}\n"
        f"Reserves: Bldg ${prelim.reserves_building} / Cont ${prelim.reserves_content}\n"
        f"Advance: Bldg ${prelim.advance_payment_building} / Cont ${prelim.advance_payment_contents}\n"
        f"\n"
        "Type 'generate' to create the XML, or the number of a field to change it."
    )

    await update.message.reply_text(summary, reply_markup=ReplyKeyboardRemove())
    return CONFIRM


async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle confirmation — generate XML or go back to edit."""
    user_id = update.effective_user.id
    session = sessions.get(user_id)
    if not session:
        return ConversationHandler.END

    answer = update.message.text.strip().lower()

    if answer in ("generate", "gen", "go", "yes", "y", "done"):
        # Start photo collection
        session["photos"] = []
        session["photo_index"] = 0

        await update.message.reply_text(
            "Data confirmed. Now send photos.\n\n"
            f"Send photo 1: {PHOTO_SEQUENCE[0]}\n\n"
            "Or type 'skip' to skip photos, or 'done' when finished."
        )
        return COLLECTING_PHOTOS

    # Try to go back to a specific question by number
    try:
        q_num = int(answer) - 1
        if 0 <= q_num < len(PRELIM_QUESTIONS):
            session["question_index"] = q_num
            await _ask_next_question(update, user_id)
            return ASKING_QUESTIONS
    except ValueError:
        pass

    await update.message.reply_text(
        "Type 'generate' to create XML, or a question number (1-17) to change an answer."
    )
    return CONFIRM


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle a photo sent during photo collection."""
    user_id = update.effective_user.id
    session = sessions.get(user_id)
    if not session:
        return ConversationHandler.END

    photo_index = session.get("photo_index", 0)
    photos = session.get("photos", [])

    # Get the largest photo version
    photo = update.message.photo[-1]  # Highest resolution
    caption = update.message.caption or ""

    # Download the photo
    photo_dir = os.path.join(os.path.dirname(__file__), "photo_temp", str(user_id))
    os.makedirs(photo_dir, exist_ok=True)

    file = await context.bot.get_file(photo.file_id)
    photo_path = os.path.join(photo_dir, f"photo_{photo_index + 1:02d}.jpg")
    await file.download_to_drive(photo_path)

    # Determine label
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

    # Prompt for next photo
    next_idx = photo_index + 1
    if next_idx < len(PHOTO_SEQUENCE):
        await update.message.reply_text(
            f"Got photo {photo_index + 1}: {label}\n\n"
            f"Send photo {next_idx + 1}: {PHOTO_SEQUENCE[next_idx]}\n"
            f"Or type 'done' to finish photos."
        )
    else:
        await update.message.reply_text(
            f"Got photo {photo_index + 1}: {label}\n\n"
            f"Send more photos or type 'done' to generate the prelim package."
        )

    return COLLECTING_PHOTOS


async def handle_photo_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages during photo collection (done/skip)."""
    user_id = update.effective_user.id
    session = sessions.get(user_id)
    if not session:
        return ConversationHandler.END

    answer = update.message.text.strip().lower()

    if answer in ("done", "finish", "generate", "go"):
        return await _generate_prelim_package(update, context, user_id)

    if answer in ("skip", "s", "no photos"):
        await update.message.reply_text("Skipping photos — generating with form + FCN card only.")
        return await _generate_prelim_package(update, context, user_id)

    await update.message.reply_text(
        "Send a photo, or type 'done' to generate the prelim package."
    )
    return COLLECTING_PHOTOS


async def _generate_prelim_package(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Generate the full prelim package (PDF + XML) and send it."""
    session = sessions[user_id]
    prelim = session["prelim"]
    photos_data = session.get("photos", [])

    await update.message.reply_text(
        f"Generating prelim package...\n"
        f"  Form: 2 pages\n"
        f"  FCN card: 1 page\n"
        f"  Photos: {len(photos_data)}"
    )

    # Build PhotoItems
    from photo_sheet import PhotoItem
    photo_items = [
        PhotoItem(
            image_path=p["path"],
            label=p["label"],
            date_taken=p["date_taken"],
            comment=p.get("comment", ""),
        )
        for p in photos_data
    ]

    # Generate the full package
    from prelim_pdf import generate_prelim_package
    out_dir = os.path.join(os.path.dirname(__file__), "output")
    result = await asyncio.to_thread(generate_prelim_package, prelim, photo_items, out_dir)

    # Send PDF
    with open(result["pdf_path"], "rb") as f:
        pdf_filename = os.path.basename(result["pdf_path"])
        await update.message.reply_document(
            document=f,
            filename=pdf_filename,
            caption=f"Preliminary Report PDF ({len(photos_data)} photos)"
        )

    # Send XML
    xml_bytes = result["xml_string"].encode("utf-8")
    xml_filename = os.path.basename(result["xml_path"])
    await update.message.reply_document(
        document=xml_bytes,
        filename=xml_filename,
        caption="Preliminary Report XML"
    )

    # Push to Supabase
    from db import push_claim
    from dataclasses import asdict
    prelim_dict = asdict(prelim)
    push_claim(
        fg_number=prelim.adjuster_file_number or "UNKNOWN",
        insured_name=prelim.insured_name,
        policy_number=prelim.policy_number,
        date_of_loss=prelim.date_of_loss,
        carrier="",
        report_type="prelim",
        confidence=1.0,
        xml_data=prelim_dict,
        xml_output=result["xml_string"],
        warnings=[],
        source="telegram",
    )
    await update.message.reply_text("Sent to dashboard for review.")

    # Clean up temp photos
    photo_dir = os.path.join(os.path.dirname(__file__), "photo_temp", str(user_id))
    if os.path.isdir(photo_dir):
        import shutil
        shutil.rmtree(photo_dir, ignore_errors=True)

    del sessions[user_id]
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the current prelim session."""
    user_id = update.effective_user.id
    if user_id in sessions:
        # Clean up temp photos
        photo_dir = os.path.join(os.path.dirname(__file__), "photo_temp", str(user_id))
        if os.path.isdir(photo_dir):
            import shutil
            shutil.rmtree(photo_dir, ignore_errors=True)
        del sessions[user_id]
    await update.message.reply_text("Prelim cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def _find_nol(fg_number: str) -> list[str]:
    """Search for NOL files matching an FG number or insured name."""
    search_dirs = [
        r"C:\Users\neill\Dropbox\RT Claims\2025 OPEN CLAIMS JULIO",
        r"C:\Users\neill\Dropbox\RT Claims\2025 OPEN CLAIMS JULIO\2024-2025 CLOSED",
        # VM paths
        "/root/Dropbox/RT Claims/2025 OPEN CLAIMS JULIO",
    ]

    matches = []
    query = fg_number.lower().replace("fg", "").strip()

    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        for root_dir, dirs, files in os.walk(search_dir):
            for f in files:
                if "nol" in f.lower() and (f.endswith(".pdf") or f.endswith(".xml")):
                    # Check if the FG number or query matches the folder path
                    full_path = os.path.join(root_dir, f)
                    if query in full_path.lower() or fg_number.lower() in full_path.lower():
                        matches.append(full_path)

    return matches


def get_prelim_handlers():
    """Return the ConversationHandler for the prelim flow."""
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
