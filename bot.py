import asyncio
import logging
import os
import re
import sys
from aiohttp import web

# Ensure UTF-8 output encoding for Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
import config
from scraper import scrape_google_maps
from pitch_generator import generate_pitch

# Configure Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Active scraping lock to prevent overlapping heavy Playwright instances
scrape_lock = asyncio.Lock()
user_niches = {}

def escape_html(text: str) -> str:
    """Safely escapes text for Telegram HTML parsing."""
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /start and /help commands."""
    welcome_text = (
        "<b>🤖 Google Maps Lead & Pitch Bot</b>\n\n"
        "I scrape Google Maps for businesses that <b>DO NOT</b> have a website, "
        "extract their contact info, and auto-generate personalized sales pitches using AI!\n\n"
        "<b>📌 How to use:</b>\n"
        "• <code>/find 10 plumbers in Miami</code> — Scrape 10 leads matching a query.\n"
        "• Type a number like <code>10</code>, <code>20</code>, <code>50</code> — Scrapes default niche.\n"
        "• <code>/setniche dental clinics in Dallas</code> — Set your default niche/location.\n"
        "• <code>/status</code> — Check system configuration and API setup.\n"
        "• <code>/help</code> — Show this help guide."
    )
    await update.message.reply_text(welcome_text, parse_mode="HTML")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /status command."""
    ai_status = "✅ Connected" if config.OPENCODE_ZEN_API_KEY else "⚠️ Missing API Key (Using built-in templates)"
    user_id = update.effective_user.id
    current_niche = user_niches.get(user_id, config.DEFAULT_NICHE)

    status_text = (
        "<b>📊 Bot Status</b>\n\n"
        f"• <b>AI Provider:</b> OpenCode Zen / OpenAI\n"
        f"• <b>AI Model:</b> <code>{config.AI_MODEL}</code>\n"
        f"• <b>AI API Status:</b> {ai_status}\n"
        f"• <b>Default Scrape Niche:</b> <code>{current_niche}</code>\n"
        f"• <b>Max Limit per Scrape:</b> <code>{config.MAX_LEADS_PER_SCRAPE}</code>\n"
        f"• <b>Headless Browser:</b> <code>{config.HEADLESS}</code>"
    )
    await update.message.reply_text(status_text, parse_mode="HTML")

async def setniche_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /setniche command."""
    user_id = update.effective_user.id
    new_niche = " ".join(context.args).strip() if context.args else ""

    if not new_niche:
        await update.message.reply_text(
            "<b>Usage:</b> <code>/setniche plumbers in Miami</code>",
            parse_mode="HTML"
        )
        return

    user_niches[user_id] = new_niche
    await update.message.reply_text(
        f"✅ Default niche updated to: <b>{escape_html(new_niche)}</b>",
        parse_mode="HTML"
    )

async def run_scrape_and_send(update: Update, query: str, count: int):
    """Core function to execute scrape, generate pitches, and deliver cards."""
    if scrape_lock.locked():
        await update.message.reply_text(
            "⏳ Another scrape job is currently running. Please wait a moment and try again."
        )
        return

    async with scrape_lock:
        status_msg = await update.message.reply_text(
            f"🔍 <b>Starting Google Maps Scrape</b>\n\n"
            f"• <b>Query:</b> <code>{escape_html(query)}</code>\n"
            f"• <b>Target Qualified Leads:</b> <code>{count}</code> (without website)\n"
            f"⏳ Launching headless scraper... Please wait.",
            parse_mode="HTML"
        )

        last_update_count = 0

        async def progress_update(found_count: int, total_limit: int, current_name: str):
            nonlocal last_update_count
            if found_count > last_update_count:
                last_update_count = found_count
                try:
                    await status_msg.edit_text(
                        f"🔍 <b>Scraping Google Maps...</b>\n\n"
                        f"• <b>Query:</b> <code>{escape_html(query)}</code>\n"
                        f"• <b>Progress:</b> <code>{found_count}/{total_limit}</code> qualified leads found!\n"
                        f"• <b>Latest Found:</b> {escape_html(current_name)} (No website)",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

        try:
            leads = await asyncio.wait_for(
                scrape_google_maps(
                    query=query,
                    limit=count,
                    progress_callback=progress_update
                ),
                timeout=120.0
            )

            if not leads:
                await status_msg.edit_text(
                    f"❌ <b>No leads found without a website</b> for query: <code>{escape_html(query)}</code>.\n"
                    f"Try searching a different location or niche!",
                    parse_mode="HTML"
                )
                return

            await status_msg.edit_text(
                f"✅ <b>Scrape Completed!</b>\n"
                f"Found <b>{len(leads)}</b> qualified businesses without a website.\n"
                f"Sending individual lead cards with AI sales pitches now...",
                parse_mode="HTML"
            )

            # Process and send each lead card
            for index, lead in enumerate(leads, 1):
                # Generate AI Sales Pitch
                pitch = generate_pitch(lead)

                social_text = "None listed"
                if lead.get("social_links"):
                    social_text = "\n".join([f"• <a href='{link}'>{link}</a>" for link in lead["social_links"]])

                maps_url = lead.get("maps_url", "")
                maps_link_html = f"<a href='{maps_url}'>View on Google Maps</a>" if maps_url else "N/A"

                card_html = (
                    f"<b>🎯 LEAD CARD #{index}/{len(leads)}</b>\n\n"
                    f"🏢 <b>Name:</b> {escape_html(lead['name'])}\n"
                    f"🏷️ <b>Category:</b> {escape_html(lead['category'])}\n"
                    f"⭐ <b>Rating:</b> {escape_html(lead['rating'])} ⭐ ({escape_html(lead['reviews'])} reviews)\n"
                    f"📞 <b>Phone:</b> <code>{escape_html(lead['phone'])}</code>\n"
                    f"📍 <b>Address:</b> {escape_html(lead['address'])}\n"
                    f"🌐 <b>Website:</b> ❌ <i>NO WEBSITE FOUND</i>\n"
                    f"🔗 <b>Maps Link:</b> {maps_link_html}\n"
                    f"📲 <b>Social Profiles:</b>\n{social_text}\n\n"
                    f"💡 <b>AI Cold DM Pitch (Copy & Send):</b>\n"
                    f"<code>{escape_html(pitch)}</code>"
                )

                await update.message.reply_text(
                    card_html,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                # Small delay between messages to avoid rate limits
                await asyncio.sleep(0.8)

        except Exception as e:
            logger.error(f"Error during scrape job execution: {e}")
            await update.message.reply_text(
                f"⚠️ An error occurred while scraping: <code>{escape_html(str(e))}</code>",
                parse_mode="HTML"
            )

async def find_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /find command: e.g. /find 10 plumbers in Miami."""
    if not context.args:
        await update.message.reply_text(
            "<b>Usage:</b> <code>/find 10 plumbers in Miami</code>",
            parse_mode="HTML"
        )
        return

    full_arg = " ".join(context.args).strip()
    match = re.match(r"^(\d+)\s+(.+)$", full_arg)

    if match:
        count = min(int(match.group(1)), config.MAX_LEADS_PER_SCRAPE)
        query = match.group(2).strip()
    else:
        user_id = update.effective_user.id
        count = 10
        query = full_arg

    await run_scrape_and_send(update, query, count)

async def text_number_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for plain text messages containing numbers like '10' or '25'."""
    text = update.message.text.strip()
    user_id = update.effective_user.id
    default_niche = user_niches.get(user_id, config.DEFAULT_NICHE)

    if text.isdigit():
        count = min(int(text), config.MAX_LEADS_PER_SCRAPE)
        if count <= 0:
            await update.message.reply_text("Please enter a number between 1 and 100.")
            return
        
        await update.message.reply_text(
            f"👌 Received count <b>{count}</b>. Using niche: <b>{escape_html(default_niche)}</b>\n"
            f"<i>Tip: Use <code>/setniche &lt;niche&gt;</code> to change your default niche.</i>",
            parse_mode="HTML"
        )
        await run_scrape_and_send(update, default_niche, count)

async def post_init(application: Application):
    """Starts a lightweight web server for Render health checks."""
    app = web.Application()
    async def handle_health(request):
        return web.Response(text="Google Maps Telegram Lead Bot is running!")
    
    app.router.add_get("/", handle_health)
    app.router.add_get("/health", handle_health)
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "10000"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health check web server running on 0.0.0.0:{port}")

def main():
    """Main application entrypoint."""
    config.validate_config()

    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is missing! Set TELEGRAM_BOT_TOKEN in .env file.")
        print("\n[ERROR] TELEGRAM_BOT_TOKEN not found! Please create a .env file with your token.\n")
        return

    # Build python-telegram-bot application with post_init health server
    application = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Add Command Handlers
    application.add_handler(CommandHandler(["start", "help"], start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("setniche", setniche_command))
    application.add_handler(CommandHandler("find", find_command))

    # Add Number Text Handler (1-100)
    application.add_handler(MessageHandler(filters.Regex(r"^\d+$"), text_number_handler))

    logger.info("Bot starting polling loop...")
    print("🚀 Telegram Bot is running! Send commands via Telegram.")
    
    # Run polling loop
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
