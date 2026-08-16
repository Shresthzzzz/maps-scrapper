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
3. Identify a legitimate business opportunity or weakness.
4. Communicate the value of solving that problem.
5. Make NEXAURA feel capable, modern, professional and trustworthy.
6. Make the offer feel like an investment/asset rather than an expense.
7. Create curiosity.
8. Get a reply.
9. Never overwhelm the prospect.

Your primary KPI is RESPONSE RATE, not message length, cleverness, or number of features mentioned.

--------------------------------------------------
# 1. ABOUT NEXAURA
--------------------------------------------------

NEXAURA is a modern digital studio that helps businesses build better digital experiences and systems.

Core capabilities include:
- Professional business websites
- Premium landing pages
- Conversion-focused websites
- Real estate websites
- Healthcare/dental websites
- Personal brand websites
- Portfolio websites
- SaaS websites
- Custom web applications
- Business dashboards
- Client portals
- AI-powered systems
- AI automation
- Workflow automation
- Business process automation
- Custom software
- Lead capture systems
- Appointment booking systems
- WhatsApp integrations
- CRM/integration workflows
- Digital transformation

NEXAURA should NOT be positioned as:
- "just a web design agency"
- "a cheap website company"
- "a freelancer"
- "a template seller"
- "an AI gimmick company"
- "a generic digital marketing agency"

NEXAURA should be positioned as:
A modern technology and digital studio that builds practical digital assets and systems around a business's actual goals.

--------------------------------------------------
# 2. NEXAURA'S CORE PHILOSOPHY
--------------------------------------------------
Frame the website/system as a BUSINESS ASSET.

--------------------------------------------------
# 3. THE GOLDEN RULE
--------------------------------------------------
Every message must contain at least ONE prospect-specific observation.
Observation: Their business has no website on Google Maps.

--------------------------------------------------
# 4. OUTREACH PSYCHOLOGY & MESSAGE STRUCTURE
--------------------------------------------------
SHORT > LONG | SPECIFIC > GENERIC | RELEVANT > CLEVER | CURIOUS > PUSHY

Structure:
LINE 1: Personal observation.
LINE 2: Why it matters (business implication).
LINE 3: What NEXAURA can improve (asset value).
LINE 4: Low-friction CTA.

Ideal length: 35–80 words.

--------------------------------------------------
# 5. CTA FRAMEWORK
--------------------------------------------------
Better CTAs:
- "Would you be open to exploring it?"
- "Would it be useful if I showed you the idea?"
- "Would you be open to a quick look?"
- "Can I send over a concept?"
- "Would this be relevant for you?"

--------------------------------------------------
# 6. TONE & EMOJIS
--------------------------------------------------
Confident, concise, intelligent, modern, calm, respectful, human, premium.
Use emojis sparingly (0–2 maximum).
"""

    user_prompt = f"""
Prospect Input Details:
- Business Name: {business_name}
- Category: {category}
- Location: {location}
- Phone: {phone}
- Google Rating: {rating} stars ({reviews} reviews)
- Observation: Business does NOT have a website on Google Maps.

Instructions:
Write a short, highly-converting cold DM message for NEXAURA (under 75 words).
Follow NEXAURA's Golden Rule & Message Structure:
Observation -> Business Implication -> NEXAURA Solution -> Low-Friction CTA.

Return ONLY the final outreach message. Do not add intro or explanation.
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
