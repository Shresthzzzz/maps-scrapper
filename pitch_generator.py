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
    Generates a unique, hyper-personalized cold DM pitch for a business lacking a website.
    Every pitch is uniquely written based on the business's specific name, category, rating, and location.
    """
    business_name = lead.get("name", "Business")
    category = lead.get("category", "Local Business")
    location = lead.get("address", "your local area")
    phone = lead.get("phone", "N/A")
    rating = lead.get("rating", "N/A")
    reviews = lead.get("reviews", "N/A")

    # Dynamic profession audience mapping
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
    else:
        audience = "customer"
        goal = "bookings and inquiries"

    # Multiple diverse fallback templates for offline mode
    fallbacks = [
        (
            f"Hi {business_name} team,\n\n"
            f"I love what you've built—your online reputation ({rating}⭐) is already strong! However, we noticed a few quick technical tweaks that could significantly improve your {audience} user experience and streamline operations.\n\n"
            f"At Nexaura, we help businesses scale by automating appointment systems, upgrading websites, and building out custom tech solutions.\n\n"
            f"Would you be open to a quick 10-minute chat this week to see how we can help you streamline {goal}? Let me know what day and time works best for you.\n\n"
            f"Best,\n\nNexaura"
        ),
        (
            f"Hey {business_name} team 👋,\n\n"
            f"I was looking through local {category} businesses in {location} and noticed your Google profile has impressive feedback ({rating}⭐). "
            f"One major opportunity stood out—you don't have a website attached to Google Maps yet, which means prospective {audience}s are clicking over to competitors instead.\n\n"
            f"We're Nexaura, a digital technology studio. We build custom websites, AI booking tools, and lead capture systems that act as growth assets.\n\n"
            f"Would you be open to seeing a free 2-minute website mockup preview we created for {business_name}?\n\n"
            f"Best,\n\nNexaura"
        ),
        (
            f"Hi team at {business_name},\n\n"
            f"Your standing in {location} ({rating} stars across {reviews} reviews) caught our eye—great work! "
            f"However, missing a dedicated website on Google Maps means missing out on dozens of direct {goal} every month.\n\n"
            f"At Nexaura, we build conversion-focused websites and automated workflow solutions tailored specifically for {category} businesses.\n\n"
            f"Open to a quick 10-minute conversation to explore how we can help you capture more leads?\n\n"
            f"Best,\n\nNexaura"
        )
    ]

    # Select fallback based on hash of business name so different leads get different fallback styles
    name_hash = sum(ord(c) for c in business_name)
    template_fallback = fallbacks[name_hash % len(fallbacks)]

    client = get_ai_client()
    if not client:
        return template_fallback

    system_prompt = """You are the elite AI B2B cold outreach strategist and copywriter for Nexaura (a modern technology studio specializing in custom websites, AI automation, booking systems, and tech solutions).

YOUR MISSION: Write a unique, hyper-personalized, humanized cold DM tailored to a specific business found on Google Maps that DOES NOT have a website.

OUTREACH PHILOSOPHY & MANDATORY RULES:
1. NO ROBOTIC TEMPLATES: Every message MUST be uniquely worded and start with a fresh opening. Never send copy-paste template DMs.
2. SHOW REAL EFFORT & RECOGNITION: Compliment their specific reputation, star rating, review count, or location standing. Show you actually looked at their business.
3. HIGHLIGHT A LEGITIMATE OPPORTUNITY: Point out that having no website on Google Maps lets prospective clients/patients/buyers slip away to competitors with online sites.
4. POSITION NEXAURA AS AN ASSET: Present Nexaura's solutions (conversion-focused sites, AI booking, lead capture) as a business asset that drives growth.
5. LOW-FRICTION CTA: End with a friendly, low-pressure question (e.g. offering a quick 10-minute chat or sending a free 2-minute site preview).
6. TONE: Friendly, respectful, intelligent, modern, concise (45 to 80 words).
7. OUTPUT: Output ONLY the raw message text ready to send. No quotes, subject lines, or labels.
"""

    user_prompt = f"""Prospect Details:
- Business Name: {business_name}
- Category: {category}
- Location: {location}
- Phone: {phone}
- Google Rating: {rating} stars ({reviews} reviews)
- Status: NO WEBSITE attached to Google Maps profile

Instructions:
Write a unique, highly-personalized, humanized cold DM for Nexaura.
Make it feel custom-tailored to them. Return ONLY the final ready-to-send message.
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
                temperature=0.8,
                max_tokens=250
            )
            pitch = response.choices[0].message.content.strip()
            # Clean up thinking process leakage if model outputs internal reasoning
            if "Here's a thinking process" in pitch or "<think>" in pitch:
                if "</think>" in pitch:
                    pitch = pitch.split("</think>")[-1].strip()
                elif "Here's a thinking process:" in pitch:
                    # Keep text after the thinking section or fallback to clean structure
                    parts = pitch.split("\n\n")
                    clean_parts = [p for p in parts if not p.strip().startswith("1.") and not p.strip().startswith("2.") and "thinking process" not in p.lower() and "Role:" not in p and "Mission:" not in p and "Prospect Details:" not in p]
                    pitch = "\n\n".join(clean_parts).strip()

            if pitch and len(pitch) > 30 and "thinking process" not in pitch.lower():
                return pitch
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "FreeUsageLimitError" in err_str or "Rate limit" in err_str:
                logger.info(f"Model '{model_name}' free limit reached, trying next model...")
            else:
                logger.warning(f"AI model '{model_name}' error: {err_str}")
            continue

    return template_fallback
