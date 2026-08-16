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

    system_prompt = """You are an elite B2B cold outreach copywriter for NEXAURA, a modern technology and digital studio that builds high-converting business websites, AI systems, and lead capture workflows.

YOUR GOAL: Write a short, highly-personalized, 100% human-sounding cold DM (40 to 70 words) to a business owner who has NO website on Google Maps.

RULES FOR NEXAURA OUTREACH:
1. Write directly on behalf of NEXAURA ("We at NEXAURA", "We're NEXAURA, a digital studio").
2. Compliment their Google reputation, rating, or reviews.
3. Gently point out that lacking a website on Google Maps loses prospective clients to competitors.
4. Offer a low-friction value step from NEXAURA (asking if they'd like a quick, free 2-minute website mockup preview).
5. Keep it conversational, personal, concise, and response-focused.
6. Output ONLY the raw outreach message itself. DO NOT include subject lines, quotes, labels, or explanatory commentary.
"""

    user_prompt = f"""
Prospect Details:
- Business Name: {business_name}
- Category: {category}
- Location: {location}
- Phone: {phone}
- Rating: {rating} stars ({reviews} reviews)
- Status: NO WEBSITE on Google Maps

Instructions:
Write a short, high-converting cold DM message for NEXAURA (under 60 words).
Return ONLY the final ready-to-send message.
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
