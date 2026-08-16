import asyncio
import logging
import urllib.parse
import re
import time
from typing import List, Dict, Callable, Optional
from playwright.async_api import async_playwright, Page
import config

logger = logging.getLogger(__name__)

async def scrape_google_maps(
    query: str,
    limit: int = 10,
    progress_callback: Optional[Callable[[int, int, str], asyncio.Task]] = None,
    exclude_names: Optional[set] = None
) -> List[Dict]:
    """
    Scrapes Google Maps for businesses matching query.
    Filters out businesses that ALREADY have a website or have been previously delivered.
    Returns qualified leads without a website.
    """
    if exclude_names is None:
        exclude_names = set()
    else:
        exclude_names = {n.strip().lower() for n in exclude_names}
    leads: List[Dict] = []
    scraped_names = set()
    
    encoded_query = urllib.parse.quote(query)
    search_url_en = f"https://www.google.com/maps/search/{encoded_query}?hl=en"
    
    logger.info(f"Starting Google Maps fast scrape for query: '{query}', target limit: {limit} non-website leads.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=config.HEADLESS,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--no-first-run",
                "--no-zygote",
                "--disable-gpu",
                "--lang=en-US,en"
            ]
        )
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            locale="en-US",
            viewport={"width": 1280, "height": 800}
        )
        
        page = await context.new_page()

        try:
            logger.info(f"🌐 Navigating to Google Maps: {search_url_en}")
            try:
                await page.goto(search_url_en, wait_until="domcontentloaded", timeout=30000)
            except Exception as ge:
                logger.warning(f"Goto warning: {ge}")

            try:
                await page.wait_for_selector("div[role='feed']", timeout=15000)
                logger.info("✅ Results feed container ready!")
            except Exception:
                logger.warning("Feed selector wait timed out, proceeding with DOM evaluation...")

            await page.wait_for_timeout(2000)

            scroll_attempts = 0
            max_scrolls = max(limit * 5, 25)
            last_lead_time = time.time()
            prev_leads_count = 0

            while len(leads) < limit and scroll_attempts < max_scrolls:
                scroll_attempts += 1
                
                # Check for 20-second stall if leads were already found but no new leads added recently
                current_time = time.time()
                if len(leads) > 0 and (current_time - last_lead_time) > 20.0:
                    logger.warning(f"⏱️ [STALL DETECTED] No new qualified leads found for 20 seconds ({len(leads)}/{limit} collected). Delivering current batch now!")
                    break

                if len(leads) > prev_leads_count:
                    last_lead_time = current_time
                    prev_leads_count = len(leads)
                
                # Fast V8 JS extraction of all current card elements in the feed
                raw_cards = await page.evaluate("""
                    () => {
                        const feed = document.querySelector("div[role='feed']");
                        if (!feed) return [];
                        const items = Array.from(feed.querySelectorAll("div:has(> a[href*='/maps/place/']), div:has(div.fontHeadlineSmall), div.Nv2pk"));
                        
                        const socialDomains = ["instagram.com", "facebook.com", "twitter.com", "x.com", "linkedin.com", "tiktok.com", "youtube.com", "wa.me", "whatsapp.com", "t.me", "linktr.ee"];

                        function isRealWebsite(href) {
                            if (!href || href.length <= 5 || href.includes("google.com")) return false;
                            const lower = href.toLowerCase();
                            // If it's a social profile link, it's NOT a real custom website!
                            if (socialDomains.some(d => lower.includes(d))) return false;
                            return true;
                        }
                        
                        const extracted = [];
                        for (const item of items) {
                            const titleEl = item.querySelector(".fontHeadlineSmall, div.qBF1Pd, span.OSrA2c");
                            if (!titleEl) continue;
                            
                            const name = titleEl.innerText.trim();
                            if (!name) continue;
                            
                            // Check website button link inside card
                            const webBtn = item.querySelector("a[aria-label*='website'], a[aria-label*='Website'], a[data-value='Website']");
                            let hasWebsite = false;
                            let websiteUrl = null;
                            let inlineSocial = [];

                            if (webBtn) {
                                const href = webBtn.getAttribute("href") || "";
                                if (isRealWebsite(href)) {
                                    hasWebsite = true;
                                    websiteUrl = href;
                                } else if (href && socialDomains.some(d => href.toLowerCase().includes(d))) {
                                    inlineSocial.push(href);
                                }
                            }
                            
                            const ratingEl = item.querySelector("span.MW4etd");
                            const reviewsEl = item.querySelector("span.UY7F9");
                            const rating = ratingEl ? ratingEl.innerText.trim() : "N/A";
                            const reviews = reviewsEl ? reviewsEl.innerText.replace(/[^0-9]/g, "") : "N/A";
                            
                            const linkEl = item.querySelector("a[href*='/maps/place/']");
                            const mapsUrl = linkEl ? linkEl.href : "";
                            const cardText = item.innerText || "";
                            
                            extracted.push({
                                name,
                                hasWebsite,
                                websiteUrl,
                                inlineSocial,
                                rating,
                                reviews,
                                mapsUrl,
                                cardText
                            });
                        }
                        return extracted;
                    }
                """)

                logger.info(f"🔄 [SCROLL #{scroll_attempts}] Found {len(raw_cards)} cards on page. Leads collected: {len(leads)}/{limit}")

                if not raw_cards and scroll_attempts > 5:
                    logger.warning("No cards returned after multiple scrolls. Ending scrape.")
                    break

                for c in raw_cards:
                    if len(leads) >= limit:
                        break
                    name = c["name"]
                    if name in scraped_names:
                        continue
                    scraped_names.add(name)

                    if name.strip().lower() in exclude_names:
                        logger.info(f"⏩ [SKIP - ALREADY DELIVERED PREVIOUSLY] '{name}'")
                        continue

                    if c["hasWebsite"]:
                        logger.info(f"⏩ [SKIP - HAS WEBSITE] '{name}' -> Website: {c['websiteUrl']}")
                        continue

                    logger.info(f"🎯 [QUALIFIED LEAD FOUND] '{name}' HAS NO WEBSITE!")

                    # Fetch phone & address by clicking on card element via JS or card text regex fallback
                    phone = "Not Listed"
                    address = "Not Listed"
                    social_links = []

                    try:
                        # Fast V8 JS click to open detail drawer without page navigation timeout
                        clicked = await page.evaluate("""
                            (targetName) => {
                                const feed = document.querySelector("div[role='feed']");
                                if (!feed) return false;
                                const items = Array.from(feed.querySelectorAll("div:has(> a[href*='/maps/place/']), div.Nv2pk"));
                                for (const item of items) {
                                    const titleEl = item.querySelector(".fontHeadlineSmall, div.qBF1Pd, span.OSrA2c");
                                    if (titleEl && titleEl.innerText.trim().toLowerCase() === targetName.toLowerCase()) {
                                        const link = item.querySelector("a[href*='/maps/place/']") || titleEl;
                                        link.click();
                                        return true;
                                    }
                                }
                                return false;
                            }
                        """, name)

                        if clicked:
                            await page.wait_for_timeout(1200)

                            # 1. Phone from side drawer
                            phone_el = page.locator("button[data-item-id^='phone:']").first
                            if await phone_el.count() > 0:
                                phone_attr = await phone_el.get_attribute("aria-label")
                                phone = phone_attr.replace("Phone: ", "").strip() if phone_attr else (await phone_el.inner_text()).strip()

                            # 2. Address from side drawer
                            address_el = page.locator("button[data-item-id='address']").first
                            if await address_el.count() > 0:
                                addr_attr = await address_el.get_attribute("aria-label")
                                address = addr_attr.replace("Address: ", "").strip() if addr_attr else (await address_el.inner_text()).strip()

                            # 3. Social links from side drawer
                            social_links = await page.evaluate("""
                                () => {
                                    const links = Array.from(document.querySelectorAll("a[href]"));
                                    const domains = ["instagram.com", "facebook.com", "twitter.com", "x.com", "linkedin.com", "tiktok.com", "wa.me", "whatsapp.com"];
                                    const found = [];
                                    for (const l of links) {
                                        const href = l.href || "";
                                        if (domains.some(d => href.toLowerCase().includes(d))) {
                                            if (!found.includes(href)) found.push(href);
                                        }
                                    }
                                    return found;
                                }
                            """)
                    except Exception as de:
                        logger.warning(f"Could not extract drawer for '{name}': {de}")

                    # Regex fallback for phone number from card text if drawer extraction was empty
                    card_text = c.get("cardText", "")
                    if phone == "Not Listed" and card_text:
                        phone_match = re.search(r'(\+?\d{1,4}[-.\s]?)?(\(?\d{2,5}\)?[-.\s]?)?\d{3,5}[-.\s]?\d{3,5}', card_text)
                        if phone_match and len(phone_match.group(0).strip()) >= 7:
                            phone = phone_match.group(0).strip()

                    # Fallback address from card text if drawer address was empty
                    if address == "Not Listed" and card_text:
                        lines = [l.strip() for l in card_text.split('\n') if l.strip()]
                        # Usually line 1 is Name, line 2 is Rating, line 3 is Category, line 4 is Address
                        for line in lines[2:]:
                            if name.lower() not in line.lower() and not re.search(r'^\d+\.\d+', line) and "stars" not in line.lower() and len(line) > 5:
                                address = line
                                break

                    if c.get("inlineSocial"):
                        for sl in c["inlineSocial"]:
                            if sl not in social_links:
                                social_links.append(sl)

                    lead = {
                        "name": name,
                        "category": query.split(" in ")[0] if " in " in query else query,
                        "address": address,
                        "phone": phone,
                        "rating": c["rating"],
                        "reviews": c["reviews"],
                        "maps_url": c["mapsUrl"] or page.url,
                        "has_website": False,
                        "social_links": social_links
                    }

                    leads.append(lead)
                    logger.info(f"✅ [LEAD STORED #{len(leads)}] '{name}' | Phone: {phone}")

                    if progress_callback:
                        try:
                            if asyncio.iscoroutinefunction(progress_callback):
                                await progress_callback(len(leads), limit, name)
                            else:
                                progress_callback(len(leads), limit, name)
                        except Exception as pe:
                            logger.error(f"Error in progress callback: {pe}")

                # Scroll down feed
                if len(leads) < limit:
                    await page.evaluate("""
                        const feed = document.querySelector("div[role='feed']");
                        if (feed) feed.scrollTop = feed.scrollHeight;
                    """)
                    await page.wait_for_timeout(800)

        except Exception as e:
            logger.error(f"❌ [SCRAPER FATAL ERROR] {e}", exc_info=True)
        finally:
            await context.close()
            await browser.close()

    logger.info(f"Scrape completed. Found {len(leads)} qualified leads without website.")
    return leads
