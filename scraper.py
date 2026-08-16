import asyncio
import logging
import urllib.parse
import re
from typing import List, Dict, Callable, Optional
from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeoutError
import config

logger = logging.getLogger(__name__)

# Social Media regex patterns for extraction
SOCIAL_DOMAINS = ["instagram.com", "facebook.com", "twitter.com", "x.com", "linkedin.com", "tiktok.com"]

async def dismiss_google_consent(page: Page):
    """Dismisses Google cookie/consent banners if they appear."""
    try:
        consent_button = page.locator("button:has-text('Accept all'), button:has-text('I agree'), button:has-text('Alle akzeptieren')")
        if await consent_button.count() > 0 and await consent_button.first.is_visible():
            await consent_button.first.click()
            await page.wait_for_timeout(1000)
    except Exception:
        pass

async def scrape_google_maps(
    query: str,
    limit: int = 10,
    progress_callback: Optional[Callable[[int, int, str], asyncio.Task]] = None
) -> List[Dict]:
    """
    Scrapes Google Maps for businesses matching query.
    Filters out businesses that ALREADY have a website.
    Returns leads without a website.
    """
    leads: List[Dict] = []
    scraped_names = set()
    
    encoded_query = urllib.parse.quote(query)
    search_url = f"https://www.google.com/maps/search/{encoded_query}"
    
    logger.info(f"Starting Google Maps scrape for query: '{query}', targeting max {limit} leads without website.")

    async with async_playwright() as p:
        # Launch Chromium with stealth flags optimized for Render container environment
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
            await page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
            await dismiss_google_consent(page)
            await page.wait_for_timeout(3000)

            # Locate the results feed panel
            feed_selector = "div[role='feed']"
            try:
                await page.wait_for_selector(feed_selector, timeout=15000)
            except PlaywrightTimeoutError:
                logger.warning("Results feed selector not found. Retrying alternate selector...")

            # Scroll and gather items
            items_processed = 0
            attempts = 0
            max_attempts = limit * 4

            while len(leads) < limit and attempts < max_attempts:
                attempts += 1
                
                # Get list of business cards
                cards = page.locator("div.Nv2pk, a.hfA8B, div[role='article']")
                card_count = await cards.count()

                if card_count == 0:
                    logger.warning("No business cards found on page yet. Waiting...")
                    await page.wait_for_timeout(2000)
                    if attempts > 5:
                        break
                    continue

                # Scroll down the feed container to load more items
                try:
                    await page.evaluate("""
                        const feed = document.querySelector("div[role='feed']");
                        if (feed) {
                            feed.scrollTop = feed.scrollHeight;
                        } else {
                            window.scrollBy(0, 1000);
                        }
                    """)
                    await page.wait_for_timeout(1500)
                except Exception:
                    pass

                # Iterate through visible cards
                for i in range(card_count):
                    if len(leads) >= limit:
                        break

                    try:
                        card = cards.nth(i)
                        
                        # Extract title / name
                        name_el = card.locator("div.qBF1Pd, .fontHeadlineSmall, span.OSrA2c").first
                        if await name_el.count() == 0:
                            continue
                        
                        name = (await name_el.inner_text()).strip()
                        if not name or name in scraped_names:
                            continue

                        # Check if card directly displays website icon / button in listing
                        website_button = card.locator("a[aria-label*='website'], a[data-value='Website'], a[aria-label*='Website']")
                        has_website = False
                        website_url = None

                        if await website_button.count() > 0:
                            website_url = await website_button.first.get_attribute("href")
                            if website_url and len(website_url) > 5 and not "google.com" in website_url:
                                has_website = True

                        # Click on card to open detailed view panel
                        try:
                            await name_el.click(timeout=3000)
                            await page.wait_for_timeout(1500)
                        except Exception:
                            continue

                        # Check detailed panel for authority website button
                        detail_website = page.locator("a[data-item-id='authority'], a[aria-label*='website'], a[aria-label*='Website']")
                        if await detail_website.count() > 0:
                            href = await detail_website.first.get_attribute("href")
                            if href and len(href) > 5 and "google.com" not in href:
                                has_website = True
                                website_url = href

                        scraped_names.add(name)

                        # FILTER RULE: If business HAS a website, SKIP IT!
                        if has_website:
                            logger.info(f"Skipping '{name}' - Has website: {website_url}")
                            continue

                        # Extracted qualified lead (NO WEBSITE)
                        logger.info(f"QUALIFIED LEAD FOUND (No Website): '{name}'")

                        # Extract Rating & Reviews
                        rating = "N/A"
                        reviews = "N/A"
                        rating_el = page.locator("div.F72Vs span.MW4etd, span.MW4etd").first
                        if await rating_el.count() > 0:
                            rating = await rating_el.inner_text()
                        
                        reviews_el = page.locator("div.F72Vs span.UY7F9, span.UY7F9").first
                        if await reviews_el.count() > 0:
                            rev_text = await reviews_el.inner_text()
                            reviews = re.sub(r"[^\d]", "", rev_text) or "N/A"

                        # Extract Phone Number
                        phone = "Not Listed"
                        phone_el = page.locator("button[data-item-id^='phone:']").first
                        if await phone_el.count() > 0:
                            phone_attr = await phone_el.get_attribute("aria-label")
                            if phone_attr:
                                phone = phone_attr.replace("Phone: ", "").strip()
                            else:
                                phone = (await phone_el.inner_text()).strip()

                        # Extract Address
                        address = "Not Listed"
                        address_el = page.locator("button[data-item-id='address']").first
                        if await address_el.count() > 0:
                            addr_attr = await address_el.get_attribute("aria-label")
                            if addr_attr:
                                address = addr_attr.replace("Address: ", "").strip()
                            else:
                                address = (await address_el.inner_text()).strip()

                        # Extract Category
                        category = query.split(" in ")[0] if " in " in query else query
                        cat_el = page.locator("button.DkEaL").first
                        if await cat_el.count() > 0:
                            category = await cat_el.inner_text()

                        # Extract Google Maps current URL
                        maps_url = page.url

                        # Search detail pane for social media links
                        social_links = []
                        all_links = await page.locator("a[href]").all()
                        for link in all_links:
                            try:
                                href = await link.get_attribute("href")
                                if href and any(dom in href.lower() for dom in SOCIAL_DOMAINS):
                                    if href not in social_links:
                                        social_links.append(href)
                            except Exception:
                                pass

                        lead = {
                            "name": name,
                            "category": category,
                            "address": address,
                            "phone": phone,
                            "rating": rating,
                            "reviews": reviews,
                            "maps_url": maps_url,
                            "has_website": False,
                            "social_links": social_links
                        }

                        leads.append(lead)

                        if progress_callback:
                            try:
                                if asyncio.iscoroutinefunction(progress_callback):
                                    await progress_callback(len(leads), limit, name)
                                else:
                                    progress_callback(len(leads), limit, name)
                            except Exception as pe:
                                logger.error(f"Error in progress callback: {pe}")

                    except Exception as card_err:
                        logger.debug(f"Error processing card index {i}: {card_err}")
                        continue

        except Exception as e:
            logger.error(f"Scraper error during execution: {e}")
        finally:
            await context.close()
            await browser.close()

    logger.info(f"Scrape finished. Found {len(leads)} qualified leads without website.")
    return leads
