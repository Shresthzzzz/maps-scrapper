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
    Generates a personalized cold DM pitch for a business lacking a website using Nexaura's Gold Standard Master Template.
    """
    business_name = lead.get("name", "Business")
    category = lead.get("category", "Local Business")
    location = lead.get("address", "your local area")
    phone = lead.get("phone", "N/A")
    rating = lead.get("rating", "N/A")
    reviews = lead.get("reviews", "N/A")

    # Dynamic profession mapping for fallback & AI guidance
    cat_lower = (category or "").lower()
    if any(w in cat_lower for w in ["clinic", "dentist", "doctor", "health", "hospital", "medical", "dermatology"]):
        audience = "patient"
        goal = "bookings"
    elif any(w in cat_lower for w in ["real estate", "realty", "property", "broker", "agent"]):
        audience = "buyer"
        goal = "inquiries"
    elif any(w in cat_lower for w in ["plumber", "electrician", "handyman", "repair", "service", "clean", "hvac"]):
        audience = "client"
        goal = "service calls"
    elif any(w in cat_lower for w in ["salon", "spa", "gym", "fitness", "barber", "beauty"]):
        audience = "client"
        goal = "appointment bookings"
    elif any(w in cat_lower for w in ["law", "lawyer", "attorney", "legal", "accounting", "consultant"]):
        audience = "client"
        goal = "consultations"
    elif any(w in cat_lower for w in ["restaurant", "cafe", "bakery", "food", "dining"]):
        audience = "customer"
        goal = "orders and table reservations"
    else:
        audience = "customer"
        goal = "bookings and inquiries"

    template_fallback = (
        f"Hi {business_name} team,\n\n"
        f"I love what you've built—your online presence is already strong. However, we noticed a few quick technical tweaks that could significantly improve your {audience} user experience and streamline operations.\n\n"
        f"At Nexaura, we help businesses scale by automating appointment systems, upgrading websites, and building out custom tech solutions.\n\n"
        f"Would you be open to a quick 10-minute chat this week to see how we can help you streamline {goal}? Let me know what day and time works best for you.\n\n"
        f"Best,\n\n"
        f"Nexaura"
    )

    client = get_ai_client()

    if not client:
        return template_fallback

    system_prompt = f"""You are the AI cold outreach copywriter for Nexaura.

YOUR MISSION: Write a cold outreach DM for any business scraped from Google Maps following this EXACT Master Template structure and tone:

--- MASTER TEMPLATE ---
Hi [Business Name] team,

I love what you've built—your online presence is already strong. However, we noticed a few quick technical tweaks that could significantly improve your [target audience: patient / client / customer / buyer] user experience and streamline operations.

At Nexaura, we help businesses scale by automating appointment systems, upgrading websites, and building out custom tech solutions.

Would you be open to a quick 10-minute chat this week to see how we can help you streamline [target goal: bookings / inquiries / service calls / consultations]? Let me know what day and time works best for you.

Best,

Nexaura
--- END TEMPLATE ---

RULES:
1. Follow the template's EXACT greeting ("Hi [Business Name] team,"), 3-paragraph structure, tone, and sign-off ("Best,\n\nNexaura").
2. Adapt terms like '[target audience]' and '[target goal]' dynamically based on the prospect's profession.
3. Output ONLY the ready-to-send DM message text. Do NOT add commentary, subject lines, or quotes.
"""

    user_prompt = f"""
Prospect Details:
- Business Name: {business_name}
- Profession / Category: {category}
- Location: {location}
- Target Audience Term: {audience}
- Target Goal Term: {goal}

Instructions:
Write the exact outreach DM using Nexaura's Master Template.
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
                temperature=0.4,
                max_tokens=250
            )
            pitch = response.choices[0].message.content.strip()
            if pitch and len(pitch) > 30:
                return pitch
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "FreeUsageLimitError" in err_str or "Rate limit" in err_str:
                logger.info(f"Model '{model_name}' free limit reached, trying next model...")
            else:
                logger.warning(f"AI model '{model_name}' error: {err_str}")
            continue

    return template_fallback
