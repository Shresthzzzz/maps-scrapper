import asyncio
import logging
import urllib.parse
import re
from typing import List, Dict, Callable, Optional
from playwright.async_api import async_playwright, Page
import config

logger = logging.getLogger(__name__)

async def scrape_google_maps(
    query: str,
    limit: int = 10,
    progress_callback: Optional[Callable[[int, int, str], asyncio.Task]] = None
) -> List[Dict]:
    """
    Scrapes Google Maps for businesses matching query.
    Filters out businesses that ALREADY have a website.
    Returns qualified leads without a website.
    """
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

            while len(leads) < limit and scroll_attempts < max_scrolls:
                scroll_attempts += 1
                
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
                            
                            extracted.push({
                                name,
                                hasWebsite,
                                websiteUrl,
                                inlineSocial,
                                rating,
                                reviews,
                                mapsUrl
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

                    if c["hasWebsite"]:
                        logger.info(f"⏩ [SKIP - HAS WEBSITE] '{name}' -> Website: {c['websiteUrl']}")
                        continue

                    logger.info(f"🎯 [QUALIFIED LEAD FOUND] '{name}' HAS NO WEBSITE!")

                    # Fetch phone & address by clicking on card title
                    phone = "Not Listed"
                    address = "Not Listed"
                    social_links = []

                    try:
                        title_locator = page.locator(f"text='{name}'").first
                        if await title_locator.count() > 0:
                            await title_locator.click(timeout=3000)
                            await page.wait_for_timeout(1000)

                            phone_el = page.locator("button[data-item-id^='phone:']").first
                            if await phone_el.count() > 0:
                                phone_attr = await phone_el.get_attribute("aria-label")
                                phone = phone_attr.replace("Phone: ", "").strip() if phone_attr else (await phone_el.inner_text()).strip()

                            address_el = page.locator("button[data-item-id='address']").first
                            if await address_el.count() > 0:
                                addr_attr = await address_el.get_attribute("aria-label")
                                address = addr_attr.replace("Address: ", "").strip() if addr_attr else (await address_el.inner_text()).strip()

                            social_links = await page.evaluate("""
                                () => {
                                    const links = Array.from(document.querySelectorAll("a[href]"));
                                    const domains = ["instagram.com", "facebook.com", "twitter.com", "x.com", "linkedin.com", "tiktok.com"];
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
                        logger.warning(f"Could not click detail drawer for '{name}': {de}")

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
                    await page.wait_for_timeout(1500)

        except Exception as e:
            logger.error(f"❌ [SCRAPER FATAL ERROR] {e}", exc_info=True)
        finally:
            await context.close()
            await browser.close()

    logger.info(f"Scrape completed. Found {len(leads)} qualified leads without website.")
    return leads
