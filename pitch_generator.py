import logging
from openai import OpenAI
import config

logger = logging.getLogger(__name__)

def get_ai_client():
    if not config.OPENCODE_ZEN_API_KEY:
        return None
    try:
        client = OpenAI(
            api_key=config.OPENCODE_ZEN_API_KEY,
            base_url=config.OPENCODE_ZEN_BASE_URL if config.OPENCODE_ZEN_BASE_URL else None,
            max_retries=0
        )
        return client
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI/OpenCode Zen client: {e}")
        return None

def generate_pitch(lead: dict) -> str:
    """
    Generates a personalized cold DM pitch for a business lacking a website.
    """
    business_name = lead.get("name", "Business")
    category = lead.get("category", "Local Business")
    location = lead.get("address", "your local area")
    phone = lead.get("phone", "N/A")
    rating = lead.get("rating", "N/A")
    reviews = lead.get("reviews", "N/A")

    client = get_ai_client()

    if not client:
        # Fallback high-quality template if API Key is missing or unavailable
        return (
            f"Hey team at {business_name}! 👋\n\n"
            f"I came across your high rating ({rating}⭐) on Google Maps in {location}. "
            f"I noticed your Google profile doesn't have a website attached—meaning you're likely losing dozens of prospective local clients every week to competitors.\n\n"
            f"At NEXAURA, we build modern, conversion-focused websites & lead capture systems for {category}. "
            f"Would you be open to a quick, free 2-minute site preview mockup for {business_name}?"
        )

    system_prompt = """NEXAURA — ELITE COLD OUTREACH COPYWRITER
## MASTER SYSTEM / TRAINING PROMPT

You are the dedicated AI cold-outreach strategist and copywriter for NEXAURA.

Your sole purpose is to help NEXAURA generate high-quality outbound messages that start genuine conversations with potential clients.

You are NOT a generic marketing copywriter.
You are NOT a spam generator.
You are NOT trying to make every message sound impressive.

You are a highly selective B2B outbound specialist whose priority is:
1. Get the prospect to read the message.
2. Make the prospect feel that the message was specifically written for them.
3. Identify a legitimate business opportunity or weakness (e.g. LACK OF WEBSITE ON GOOGLE MAPS).
4. Communicate the value of solving that problem.
5. Make NEXAURA feel capable, modern, professional and trustworthy.
6. Make the offer feel like an investment/asset rather than an expense.
7. Create curiosity.
8. Get a reply.
9. Never overwhelm the prospect.

Your primary KPI is RESPONSE RATE, not message length, cleverness, or number of features mentioned.

--------------------------------------------------
# ABOUT NEXAURA
--------------------------------------------------
NEXAURA is a modern digital studio that helps businesses build better digital experiences and systems.
Core capabilities: Professional business websites, Premium landing pages, Conversion-focused websites, Healthcare/dental websites, AI automation, Appointment booking systems, WhatsApp integrations, Lead capture systems.
"""

    user_prompt = f"""
Prospect Details:
- Business Name: {business_name}
- Category: {category}
- Location: {location}
- Google Rating: {rating} stars ({reviews} reviews)
- Website Status: NO WEBSITE attached on Google Maps

Instructions:
Write a short, high-converting cold DM on behalf of NEXAURA (under 100 words).
1. Compliment their Google reputation.
2. Point out that having no website on Google Maps loses prospective local clients to competitors.
3. Offer a low-friction value step from NEXAURA (e.g., asking if you can send over a quick free site preview/mockup).
4. Keep it conversational, personal, concise, and response-focused. Do not use hashtags.
"""

    candidate_models = list(dict.fromkeys([
        config.AI_MODEL, 
        "big-pickle", 
        "deepseek-v4-flash-free", 
        "mimo-v2.5-free", 
        "laguna-s-2.1-free", 
        "nemotron-3.5-lightning-free", 
        "nemotron-3-ultra-free", 
        "hy3-free"
    ]))

    for model_name in candidate_models:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=250
            )
            pitch = response.choices[0].message.content.strip()
            return pitch
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "FreeUsageLimitError" in err_str or "Rate limit" in err_str:
                logger.info(f"Model '{model_name}' free limit reached, trying next model...")
            else:
                logger.warning(f"AI model '{model_name}' error: {err_str}")
            continue

    # Return fallback template if all API calls encounter issues
    return (
        f"Hey team at {business_name}! 👋\n\n"
        f"I came across your high rating ({rating}⭐) on Google Maps in {location}. "
        f"I noticed your Google profile doesn't have a website attached—meaning you're likely losing prospective local clients to competitors.\n\n"
        f"At NEXAURA, we build modern, conversion-focused websites & lead capture systems for {category}. Could I send over a quick free 2-minute site preview mockup for {business_name}?"
    )
