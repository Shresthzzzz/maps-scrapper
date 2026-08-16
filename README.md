# 🚀 Telegram Google Maps Lead Scraper & AI Pitch Bot

An automated lead generation engine that receives commands via **Telegram**, scrapes **Google Maps** for local businesses **without a website**, enriches contact info (phone, address, Google Maps link, social profiles), and uses **OpenCode Zen / AI API** to generate high-converting cold outreach DM pitches.

---

## ✨ Features

- 📱 **Telegram Bot Interface**: Send simple commands like `/find 20 plumbers in Miami` or type any number `1-100`.
- 🔍 **Smart Website Filter**: Scrapes Google Maps via Playwright and **filters out businesses that already have a website**. Only delivers high-converting qualified leads!
- 📲 **Social Media & Contact Extraction**: Extracts phone number, rating, reviews count, Google Maps URL, and social media handles (Instagram, Facebook, Twitter, LinkedIn).
- 💡 **AI Sales Pitch Generator**: Crafts personalized cold DM pitches targeting non-website owners using OpenCode Zen / OpenAI compatible API.
- ⚡ **Render Ready (Free Tier)**: Dockerized background worker optimized for Render's free tier.

---

## 🛠️ Step 1: Create a Telegram Bot

1. Open Telegram and search for **[@BotFather](https://t.me/BotFather)**.
2. Send `/newbot` and follow the prompts to choose a bot name and username.
3. BotFather will provide your **HTTP API Token** (e.g., `7890123456:AAFd...`). Save this token!

---

## ⚙️ Step 2: Local Setup & Configuration

1. Clone or download this project folder.
2. Create a `.env` file in the root directory (copy `.env.example`):
   ```bash
   cp .env.example .env
   ```
3. Open `.env` and fill in your keys:
   ```env
   TELEGRAM_BOT_TOKEN=7890123456:AAFd...
   OPENCODE_ZEN_API_KEY=your_opencode_zen_api_key
   OPENCODE_ZEN_BASE_URL=https://opencode.ai/api/v1
   AI_MODEL=opencode/zen-1
   HEADLESS=true
   DEFAULT_NICHE=plumbers in Miami
   ```

4. Install Python dependencies and Playwright browser:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

5. Run the bot locally:
   ```bash
   python bot.py
   ```

---

## 🌐 Step 3: Deploy Free 24/7 on Render

### Option A: 1-Click Blueprint (Recommended)
1. Push this repository to **GitHub** or **GitLab**.
2. Log in to [Render.com](https://render.com).
3. Click **New +** -> **Blueprint**.
4. Connect your GitHub repository containing this code.
5. Render will automatically detect `render.yaml`.
6. Enter your `TELEGRAM_BOT_TOKEN` and `OPENCODE_ZEN_API_KEY` when prompted in Environment Variables.
7. Click **Apply**. Render will build the Docker container and start your bot!

### Option B: Manual Web/Background Worker Setup
1. On Render Dashboard, click **New +** -> **Background Worker**.
2. Connect your repository.
3. Choose **Docker** as Runtime environment.
4. Select **Free** instance plan.
5. In **Environment Variables**, add:
   - `TELEGRAM_BOT_TOKEN`: `your_bot_token`
   - `OPENCODE_ZEN_API_KEY`: `your_api_key`
   - `OPENCODE_ZEN_BASE_URL`: `https://opencode.ai/api/v1`
   - `HEADLESS`: `true`
6. Click **Create Background Worker**.

---

## 🤖 Telegram Bot Commands Reference

| Command | Usage | Description |
| :--- | :--- | :--- |
| `/start` | `/start` | Welcome guide & command overview |
| `/find` | `/find 20 gyms in Los Angeles` | Scrapes target count of businesses without website |
| `<1-100>` | `15` or `50` | Sends a number to scrape default niche |
| `/setniche` | `/setniche dental clinics in Dallas` | Updates your default niche for number shortcuts |
| `/status` | `/status` | Displays system status, API connection, and configuration |
| `/help` | `/help` | Displays help message |

---

## 💡 Example Telegram Output

```
🎯 LEAD CARD #1/10

🏢 Name: Miami Plumbers Pro
🏷️ Category: Plumber
⭐ Rating: 4.9 ⭐ (28 reviews)
📞 Phone: +1 305-555-0199
📍 Address: 123 Main St, Miami, FL
🌐 Website: ❌ NO WEBSITE FOUND
🔗 Maps Link: View on Google Maps
📲 Social Profiles:
• https://instagram.com/miami_plumbers_pro

💡 AI Cold DM Pitch (Copy & Send):
Hey team at Miami Plumbers Pro! 👋 I saw your 4.9⭐ rating on Google Maps in Miami. I noticed you don't have a website linked to your Google profile yet—which means you're missing out on dozens of local customers searching for plumbers every week! We build fast, mobile-friendly sites & online booking systems designed to double local leads. Would you be open to seeing a free 2-minute mockup I created for Miami Plumbers Pro?
```
