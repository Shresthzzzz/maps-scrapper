import os
from dotenv import load_dotenv

# Load environment variables from .env file if available
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENCODE_ZEN_API_KEY = os.getenv("OPENCODE_ZEN_API_KEY", "")
# Default base URL for OpenCode Zen / OpenAI compatible API
OPENCODE_ZEN_BASE_URL = os.getenv("OPENCODE_ZEN_BASE_URL", "https://opencode.ai/zen/v1")
AI_MODEL = os.getenv("AI_MODEL", "zen-1")

# Scraper configuration
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
DEFAULT_NICHE = os.getenv("DEFAULT_NICHE", "plumbers in Miami")
MAX_LEADS_PER_SCRAPE = int(os.getenv("MAX_LEADS_PER_SCRAPE", "100"))

def validate_config():
    missing = []
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if missing:
        print(f"[WARNING] Missing environment variables: {', '.join(missing)}")
        print("Please set them in your .env file or environment before running.")
    return len(missing) == 0
