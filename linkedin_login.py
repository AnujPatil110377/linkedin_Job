import asyncio
import sys
import os
from pathlib import Path
import json
from datetime import datetime
import logging
from playwright.async_api import async_playwright
import random
import urllib.parse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler("linkedin_scraper.log", mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class LinkedInScraper:
    def __init__(self):
        self.user_data_dir = os.path.join(str(Path.home()), ".linkedin_automation")
        self.cookies_file = os.path.join(self.user_data_dir, "cookies.json")
        os.makedirs(self.user_data_dir, exist_ok=True)
        logging.info(f"User data directory: {self.user_data_dir}")

    async def load_cookies(self, context):
        """Load cookies if they exist."""
        try:
            if os.path.exists(self.cookies_file):
                logging.info("Found existing cookies file")
                with open(self.cookies_file, 'r') as f:
                    cookies = json.load(f)
                await context.add_cookies(cookies)
                logging.info(f"Loaded {len(cookies)} cookies")
                return True
            return False
        except Exception as e:
            logging.error(f"Error loading cookies: {str(e)}")
            return False

    async def save_cookies(self, context):
        """Save cookies for future use."""
        try:
            cookies = await context.cookies()
            with open(self.cookies_file, 'w') as f:
                json.dump(cookies, f)
            logging.info(f"Saved {len(cookies)} cookies")
        except Exception as e:
            logging.error(f"Error saving cookies: {str(e)}")

    async def check_login_status(self, page):
        """Check if we're logged in by visiting LinkedIn."""
        try:
            await page.goto('https://www.linkedin.com/feed/')
            await page.wait_for_timeout(3000)
            return 'feed' in page.url or 'mynetwork' in page.url
        except Exception:
            return False

    async def scroll_page(self, page, scroll_delay=500):
        """Scroll the page to load all content."""
        try:
            prev_height = await page.evaluate('document.body.scrollHeight')
            while True:
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await page.wait_for_timeout(scroll_delay)
                new_height = await page.evaluate('document.body.scrollHeight')
                if new_height == prev_height:
                    break
                prev_height = new_height
        except Exception as e:
            logging.error(f"Error during scrolling: {str(e)}")

    async def extract_profile_info(self, profile_elem):
        """Extract all profile information in a single evaluation call."""
        try:
            profile_data = await profile_elem.evaluate('''(element) => {
                const data = {};
                
                // Get profile URL
                const anchor = element.querySelector('a.SGlfjVgIoCjdRzagDUhwgwvdZMwzddAtECE[href*="/in/"]');
                data.url = anchor ? anchor.href : null;
                
                // Get name
                const nameSpan = element.querySelector('a.SGlfjVgIoCjdRzagDUhwgwvdZMwzddAtECE span[dir="ltr"] span[aria-hidden="true"]');
                data.name = nameSpan ? nameSpan.textContent.trim() : "Name not found";
                
                // Get image URL
                const img = element.querySelector('img');
                data.image_url = img ? img.src : null;
                
                // Get designation
                const designation = element.querySelector('div.zdqSzrbjAHpnNueSDOUajcZNRGFoPfYvdRY');
                data.designation = designation ? designation.textContent.trim() : null;
                
                // Get location
                const location = element.querySelector('div.ZJlaILSysBzJXmOfoyWeXNACmszynFiQwubGk');
                data.location = location ? location.textContent.trim() : null;
                
                return data;
            }''')
            return profile_data
        except Exception as e:
            logging.error(f"Error extracting profile info: {str(e)}")
            return None

    async def scrape_profiles(self, search_query: str, max_profiles: int = 20):
        logging.info(f"Starting LinkedIn scraping for query: {search_query}")
        start_time = datetime.now()
        browser = None

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-gpu",
                        "--disable-dev-shm-usage",
                        "--no-sandbox"
                    ]
                )
                
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0 Safari/537.36'
                )
                page = await context.new_page()
                
                try:
                    cookies_loaded = await self.load_cookies(context)
                    if cookies_loaded:
                        logging.info("Checking if cookies are valid...")
                        if await self.check_login_status(page):
                            logging.info("Successfully logged in using cookies")
                        else:
                            logging.info("Cookies expired, proceeding with manual login")
                            await self.perform_login(page, context)
                    else:
                        logging.info("No cookies found, proceeding with manual login")
                        await self.perform_login(page, context)

                    if 'feed' in page.url or 'mynetwork' in page.url:
                        encoded_query = urllib.parse.quote(search_query)
                        search_url = f'https://www.linkedin.com/search/results/people/?keywords={encoded_query}&origin=SWITCH_SEARCH_VERTICAL'
                        logging.info(f"Navigating to search URL: {search_url}")
                        
                        await page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
                        await page.wait_for_timeout(2000)
                        
                        await page.wait_for_selector('.search-results-container', timeout=30000)
                        
                        logging.info("Scrolling to load all results...")
                        await self.scroll_page(page)
                        
                        logging.info("Finding profile elements...")
                        profile_elements = await page.query_selector_all('div.jlAahycHCtXuARzUjbWOsTOgMcDTRYHE')
                        logging.info(f"Found {len(profile_elements)} profile elements")
                        
                        processed_urls = set()
                        profiles_processed = 0
                        
                        # Process profiles in batches for better performance
                        batch_size = 5
                        for i in range(0, min(len(profile_elements), max_profiles), batch_size):
                            batch = profile_elements[i:min(i + batch_size, max_profiles)]
                            
                            # Extract profile information concurrently
                            tasks = [self.extract_profile_info(elem) for elem in batch]
                            profiles_data = await asyncio.gather(*tasks)
                            
                            for profile_data in profiles_data:
                                if not profile_data or not profile_data['url'] or profile_data['url'] in processed_urls:
                                    continue
                                
                                if '?' in profile_data['url']:
                                    profile_data['url'] = profile_data['url'].split('?')[0]
                                
                                if profile_data['url'] in processed_urls:
                                    continue
                                
                                processed_urls.add(profile_data['url'])
                                
                                print(f"\nProfile {profiles_processed + 1}:")
                                print("=" * 40)
                                print(f"Name: {profile_data['name']}")
                                if profile_data['designation']:
                                    print(f"Designation: {profile_data['designation']}")
                                if profile_data['location']:
                                    print(f"Location: {profile_data['location']}")
                                print(f"LinkedIn URL: {profile_data['url']}")
                                if profile_data['image_url']:
                                    print(f"Profile Image: {profile_data['image_url']}")
                                print("=" * 40)
                                
                                profiles_processed += 1
                                
                            # Small delay between batches
                            await asyncio.sleep(0.5)
                            
                    else:
                        logging.error(f"Login failed. Current URL: {page.url}")
                        
                except Exception as e:
                    logging.error(f"Error during scraping: {str(e)}", exc_info=True)
                finally:
                    if browser:
                        await browser.close()
                    
                    end_time = datetime.now()
                    duration = end_time - start_time
                    logging.info(f"Scraping completed in {duration.total_seconds():.2f} seconds")
                    
        except KeyboardInterrupt:
            logging.info("Scraping interrupted by user")
            if browser:
                await browser.close()
        except Exception as e:
            logging.error(f"Fatal error: {str(e)}", exc_info=True)
            if browser:
                await browser.close()

    async def perform_login(self, page, context):
        """Handle the login process and save cookies on success."""
        try:
            logging.info("Navigating to login page...")
            await page.goto('https://www.linkedin.com/login')
            
            await page.wait_for_selector('#username', timeout=5000)
            await page.wait_for_selector('#password', timeout=5000)
            
            await page.fill('#username', 'anujpatil917@gmail.com')
            await page.fill('#password', 'Anuj@789@anuj')
            await page.click('button[type="submit"]')
            
            await page.wait_for_timeout(5000)
            
            if 'feed' in page.url or 'mynetwork' in page.url:
                logging.info("Successfully logged in manually")
                await self.save_cookies(context)
                return True
            else:
                logging.error("Login failed")
                return False
                
        except Exception as e:
            logging.error(f"Error during login: {str(e)}")
            return False

async def main():
    logging.info("\n" + "="*50 + "\nNEW SCRAPING SESSION STARTED\n" + "="*50)
    
    try:
        scraper = LinkedInScraper()
        await scraper.scrape_profiles("hr manager coal india limited", max_profiles=20)
    except Exception as e:
        logging.error(f"Fatal error in main: {str(e)}", exc_info=True)
    finally:
        loop = asyncio.get_event_loop()
        await loop.shutdown_asyncgens()
        
if __name__ == "__main__":
    asyncio.run(main()) 