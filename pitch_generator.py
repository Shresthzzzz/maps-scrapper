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
            base_url=config.OPENCODE_ZEN_BASE_URL if config.OPENCODE_ZEN_BASE_URL else None
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
            f"I saw your high rating ({rating}⭐) on Google Maps in {location}. "
            f"Notice you don't have a website linked to your Google profile yet—which means you're missing out on dozens of new customers searching for {category} every week!\n\n"
            f"We build fast, high-converting websites & online booking systems designed to double local leads. "
            f"Would you be open to seeing a free 2-minute mockup I created for {business_name}?"
        )

    system_prompt = (
        "You are an expert sales copywriter specializing in web design and digital marketing agency cold outreach. "
        "Your task is to write a short, highly compelling, personal, non-spammy cold DM pitch (under 120 words) "
        "to a local business owner who DOES NOT have a website on Google Maps."
    )

    user_prompt = f"""
Business Name: {business_name}
Category: {category}
Address/Location: {location}
Rating: {rating} stars ({reviews} reviews)

Instructions:
1. Briefly compliment their Google rating/reputation.
2. Point out that they currently lack a website link on Google Maps, missing valuable local searches.
3. Propose building a clean, modern website/booking page tailored to get them more paying clients.
4. End with a low-friction Call To Action (asking if you can send a quick free demo/mockup link).
5. Keep it natural, professional, and friendly. Do not use hashtags.
"""

    candidate_models = list(dict.fromkeys([config.AI_MODEL, "deepseek-v4-flash-free", "mimo-v2.5-free", "big-pickle", "laguna-s-2.1-free"]))

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
            logger.warning(f"AI pitch generation failed for model '{model_name}': {e}")
            continue

    # Return fallback template if all API calls encounter issues
    return (
        f"Hey team at {business_name}! 👋\n\n"
        f"I came across your business on Google Maps ({rating}⭐). "
        f"I noticed your Google profile doesn't have a website attached. You're likely losing 30-40% of prospective clients who look for an online site before calling.\n\n"
        f"We specialize in modern web designs for {category}. Could I send over a quick free site preview for {business_name}?"
    )
