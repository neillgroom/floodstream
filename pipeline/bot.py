"""
FloodStream Telegram Bot

Julio sends a message with a PDF filename → bot runs the pipeline → returns XML.

Commands:
  /final <filename>  — Generate Final XML from a PDF in Dropbox
  /status            — Check bot status
  /help              — Show available commands

The bot looks for PDFs in the Dropbox RT Claims folder.
Only whitelisted Telegram user IDs can use it.
"""

import asyncio
import glob
import logging
import os
import sys
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Add pipeline directory to path
sys.path.insert(0, os.path.dirname(__file__))

from pdf_extractor import extract_text_from_pdf, extract_claim_metadata
from ai_validation import validate_extraction, ANTHROPIC_API_KEY
from mapper import map_to_adjuster_data
from xml_builder import build_xml

# --- Configuration ---

# Load from .env
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

# Whitelisted user IDs (Neill + Julio)
ALLOWED_USERS = set()
allowed_str = os.environ.get("ALLOWED_TELEGRAM_USERS", _env.get("ALLOWED_TELEGRAM_USERS", ""))
if allowed_str:
    ALLOWED_USERS = {int(uid.strip()) for uid in allowed_str.split(",") if uid.strip()}

# PDF search paths
PDF_SEARCH_PATHS = [
    r"C:\Users\neill\Dropbox\RT Claims\2025 XACTIMATE FILES\7 Final",
    r"C:\Users\neill\Dropbox\RT Claims\2025 XACTIMATE FILES\7 Final\BACKUP",
    r"C:\Users\neill\Dropbox\RT Claims\2025 XACTIMATE FILES\Backup",
    r"C:\Users\neill\Downloads",
    # VM paths
    "/root/Dropbox/RT Claims/2025 XACTIMATE FILES/7 Final",
    "/root/Dropbox/RT Claims/2025 XACTIMATE FILES/7 Final/BACKUP",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("floodstream-bot")


def is_authorized(update: Update) -> bool:
    """Check if user is whitelisted. If no whitelist configured, allow all (dev mode)."""
    if not ALLOWED_USERS:
        return True  # Dev mode — no whitelist
    return update.effective_user.id in ALLOWED_USERS


def find_pdf(query: str) -> list[str]:
    """
    Find PDF files matching a query string.
    Searches all configured paths. Returns list of matching full paths.
    """
    matches = []
    query_lower = query.lower().strip()

    for search_dir in PDF_SEARCH_PATHS:
        if not os.path.isdir(search_dir):
            continue

        for f in os.listdir(search_dir):
            if not f.lower().endswith(".pdf"):
                continue
            if query_lower in f.lower():
                matches.append(os.path.join(search_dir, f))

    # Deduplicate by filename
    seen = set()
    unique = []
    for m in matches:
        name = os.path.basename(m)
        if name not in seen:
            seen.add(name)
            unique.append(m)

    return unique


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help message."""
    if not is_authorized(update):
        await update.message.reply_text("Not authorized.")
        return

    await update.message.reply_text(
        "FloodStream Bot\n\n"
        "Commands:\n"
        "  /final <name> - Generate Final XML from PDF\n"
        "  /prelim <FG#> - Guided Preliminary Report\n"
        "  /search <name> - Find PDFs matching a name\n"
        "  /status - Check bot status\n"
        "  /cancel - Cancel current prelim session\n"
        "  /help - This message\n\n"
        "Examples:\n"
        "  /final BAILEY\n"
        "  /prelim FG151849\n"
        "  /search HUERTA\n\n"
        "You can also send a PDF file directly for Final XML generation."
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check bot status."""
    if not is_authorized(update):
        await update.message.reply_text("Not authorized.")
        return

    ai_status = "Ready" if ANTHROPIC_API_KEY else "No API key (regex-only mode)"
    paths_available = sum(1 for p in PDF_SEARCH_PATHS if os.path.isdir(p))

    await update.message.reply_text(
        f"FloodStream Bot Status\n\n"
        f"AI Validation: {ai_status}\n"
        f"Search paths: {paths_available} accessible\n"
        f"Your user ID: {update.effective_user.id}"
    )


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search for PDFs matching a name."""
    if not is_authorized(update):
        await update.message.reply_text("Not authorized.")
        return

    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("Usage: /search <name>\nExample: /search BAILEY")
        return

    matches = find_pdf(query)
    if not matches:
        await update.message.reply_text(f"No PDFs found matching '{query}'")
        return

    lines = [f"Found {len(matches)} PDF(s) matching '{query}':\n"]
    for m in matches[:10]:
        size_mb = os.path.getsize(m) / (1024 * 1024)
        lines.append(f"  {os.path.basename(m)} ({size_mb:.1f} MB)")

    if len(matches) > 10:
        lines.append(f"\n  ...and {len(matches) - 10} more")

    await update.message.reply_text("\n".join(lines))


async def cmd_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate Final XML from a PDF."""
    if not is_authorized(update):
        await update.message.reply_text("Not authorized.")
        return

    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("Usage: /final <name>\nExample: /final BAILEY")
        return

    matches = find_pdf(query)
    if not matches:
        await update.message.reply_text(f"No PDFs found matching '{query}'")
        return

    if len(matches) > 1:
        lines = [f"Multiple matches for '{query}'. Be more specific:\n"]
        for m in matches[:10]:
            lines.append(f"  {os.path.basename(m)}")
        await update.message.reply_text("\n".join(lines))
        return

    pdf_path = matches[0]
    pdf_name = os.path.basename(pdf_path)

    await update.message.reply_text(f"Processing: {pdf_name}\nExtracting data...")

    try:
        result = await asyncio.to_thread(_run_pipeline, pdf_path)

        if result["success"]:
            # Send summary
            meta = result["meta"]
            summary = (
                f"Extraction complete ({result['confidence']:.0%} confidence)\n\n"
                f"Insured: {meta.insured_name}\n"
                f"Policy: {meta.policy_number}\n"
                f"DOL: {meta.date_of_loss}\n"
                f"Bldg RCV: ${meta.bldg_rcv_loss}\n"
                f"Bldg Payable: ${meta.bldg_claim_payable}\n"
                f"Cont Payable: ${meta.cont_claim_payable or 'N/A'}\n"
                f"RC Qualified: {'Yes' if meta.qualifies_for_rc else 'No'}\n"
            )

            if result.get("corrections"):
                summary += f"\nAI corrections: {result['corrections']}"

            await update.message.reply_text(summary)

            # Send XML file
            xml_bytes = result["xml"].encode("utf-8")
            xml_filename = pdf_name.rsplit(".", 1)[0] + "_FINAL.xml"

            await update.message.reply_document(
                document=xml_bytes,
                filename=xml_filename,
                caption="Generated AdjusterData XML"
            )
        else:
            await update.message.reply_text(
                f"Extraction failed for {pdf_name}\n\n"
                f"Confidence: {result.get('confidence', 0):.0%}\n"
                f"Error: {result.get('error', 'Unknown')}"
            )

    except Exception as e:
        log.exception(f"Error processing {pdf_name}")
        await update.message.reply_text(f"Error: {type(e).__name__}: {e}")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle a PDF file sent directly via Telegram."""
    if not is_authorized(update):
        await update.message.reply_text("Not authorized.")
        return

    doc = update.message.document
    if not doc.file_name.lower().endswith(".pdf"):
        await update.message.reply_text("Please send a PDF file.")
        return

    await update.message.reply_text(f"Received: {doc.file_name}\nDownloading and processing...")

    try:
        # Download the file
        file = await context.bot.get_file(doc.file_id)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
            await file.download_to_drive(tmp_path)

        # Process
        result = await asyncio.to_thread(_run_pipeline, tmp_path)

        if result["success"]:
            meta = result["meta"]
            summary = (
                f"Extraction complete ({result['confidence']:.0%} confidence)\n\n"
                f"Insured: {meta.insured_name}\n"
                f"Policy: {meta.policy_number}\n"
                f"DOL: {meta.date_of_loss}\n"
                f"Bldg Payable: ${meta.bldg_claim_payable}\n"
            )
            await update.message.reply_text(summary)

            xml_bytes = result["xml"].encode("utf-8")
            xml_filename = doc.file_name.rsplit(".", 1)[0] + "_FINAL.xml"
            await update.message.reply_document(
                document=xml_bytes,
                filename=xml_filename,
                caption="Generated AdjusterData XML"
            )
        else:
            await update.message.reply_text(f"Extraction failed: {result.get('error', 'Unknown')}")

        # Cleanup
        os.unlink(tmp_path)

    except Exception as e:
        log.exception(f"Error processing uploaded PDF")
        await update.message.reply_text(f"Error: {type(e).__name__}: {e}")


def _run_pipeline(pdf_path: str) -> dict:
    """Run the full extraction pipeline. Called from async context via to_thread."""
    result = {
        "success": False,
        "confidence": 0,
        "meta": None,
        "xml": None,
        "corrections": 0,
        "error": None,
    }

    try:
        # Tier 1: regex
        text = extract_text_from_pdf(pdf_path)
        if not text or len(text) < 100:
            result["error"] = "Could not extract text from PDF (may be a photo sheet or scanned doc)"
            return result

        meta = extract_claim_metadata(text)

        # Tier 2 + 3: AI validation
        if ANTHROPIC_API_KEY:
            meta = validate_extraction(text, meta)

        result["meta"] = meta
        result["confidence"] = meta.confidence

        # Check critical fields
        if not meta.insured_name or not meta.policy_number:
            result["error"] = "Missing critical fields (insured name or policy number)"
            return result

        # Generate XML
        data = map_to_adjuster_data(meta)
        xml = build_xml(data)
        result["xml"] = xml
        result["success"] = True

    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"

    return result


def main():
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set")
        print("  Add it to pipeline/.env:")
        print("  TELEGRAM_BOT_TOKEN=your_token_here")
        print("\n  Get a token from @BotFather on Telegram")
        sys.exit(1)

    log.info("Starting FloodStream bot...")
    log.info(f"AI validation: {'enabled' if ANTHROPIC_API_KEY else 'disabled (no API key)'}")
    log.info(f"Whitelist: {ALLOWED_USERS or 'disabled (dev mode)'}")
    log.info(f"Search paths: {sum(1 for p in PDF_SEARCH_PATHS if os.path.isdir(p))} accessible")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Prelim conversation handler (must be added BEFORE simple command handlers)
    from prelim_bot import get_prelim_handlers
    app.add_handler(get_prelim_handlers())

    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("start", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("final", cmd_final))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_document))

    log.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
