import asyncio
import sys
import os
from pathlib import Path
import json
from datetime import datetime
import logging
from typing import List
from playwright.async_api import async_playwright
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
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
        # Initialize crawl4ai
        self.crawler = AsyncWebCrawler()

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

    async def scroll_page(self, page, scroll_delay=1000):
        """Scroll the page with improved logic."""
        try:
            # Get initial scroll height
            prev_height = await page.evaluate('document.body.scrollHeight')
            
            while True:
                # Scroll down
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await page.wait_for_timeout(scroll_delay)
                
                # Get new scroll height
                new_height = await page.evaluate('document.body.scrollHeight')
                
                # Check if we've reached the bottom
                if new_height == prev_height:
                    break
                    
                prev_height = new_height
                logging.info(f"Scrolled to height: {new_height}")
                
                # Add some randomization to scroll behavior
                if random.random() < 0.3:  # 30% chance to scroll up a bit
                    scroll_up = random.randint(100, 300)
                    await page.evaluate(f'window.scrollBy(0, -{scroll_up})')
                    await page.wait_for_timeout(random.randint(500, 1000))
                
        except Exception as e:
            logging.error(f"Error during scrolling: {str(e)}")

    async def get_crawl4ai_markdown(self, url):
        """Get markdown content using crawl4ai."""
        try:
            result = await self.crawler.arun(
                url=url,
                config=CrawlerRunConfig(
                    markdown_generator=DefaultMarkdownGenerator()
                )
            )
            if result.success:
                return result.markdown
            else:
                logging.error(f"Failed to generate markdown for {url}")
                return None
        except Exception as e:
            logging.error(f"Error generating markdown: {str(e)}")
            return None

    async def search_and_scrape_profile(self, page, profile_url):
        """Search for a LinkedIn profile URL and scrape its contents."""
        try:
            # Add random delay before search
            await asyncio.sleep(random.uniform(2, 5))
            
            # Randomize viewport size slightly
            width = random.randint(1800, 1920)
            height = random.randint(900, 1080)
            await page.set_viewport_size({"width": width, "height": height})
            
            # Construct Google search URL with the LinkedIn profile URL
            encoded_url = urllib.parse.quote(profile_url)
            # google_search_url = f'https://www.google.com/search?q=site:linkedin.com+{encoded_url}'
            
            # Navigate to Google search with human-like behavior
            logging.info(f"Searching on Google: {profile_url}")
            await page.goto(profile_url, wait_until='domcontentloaded', timeout=30000)
            
            # Random wait time
            await page.wait_for_timeout(random.randint(2000, 4000))
            
            # Simulate human-like scrolling before clicking
            scroll_amount = random.randint(100, 300)
            await page.mouse.move(random.randint(0, width), scroll_amount)
            await page.mouse.wheel(0, scroll_amount)
            await page.wait_for_timeout(random.randint(500, 1500))
            
            # Try to find and click the LinkedIn result with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Wait for search results to load
                    linkedin_result = await page.wait_for_selector(f'a[href^="{profile_url}"]', timeout=10000)
                    
                    if linkedin_result:
                        # Get element position
                        box = await linkedin_result.bounding_box()
                        if box:
                            # Move mouse in a human-like way (with slight randomization)
                            await page.mouse.move(
                                box['x'] + random.randint(5, int(box['width']-5)),
                                box['y'] + random.randint(5, int(box['height']-5)),
                                steps=random.randint(5, 10)
                            )
                            await page.wait_for_timeout(random.randint(200, 500))
                            
                            # Click the result
                            await linkedin_result.click()
                            await page.wait_for_timeout(random.randint(3000, 5000))
                            
                            # Wait for profile page to load with increased timeout
                            await page.wait_for_selector('.pv-top-card', timeout=45000)
                            
                            # Random delay before scrolling
                            await page.wait_for_timeout(random.randint(1000, 2000))
                            
                            # Scroll with human-like behavior
                            await self.scroll_page(page, scroll_delay=random.randint(800, 1200))
                            
                            # Additional random delay before getting markdown
                            await page.wait_for_timeout(random.randint(1000, 2000))
                            
                            # Get markdown content
                            markdown = await self.get_crawl4ai_markdown(page.url)
                            if markdown:
                                logging.info(f"Successfully generated markdown for {profile_url}")
                                return markdown
                            else:
                                logging.error(f"Failed to generate markdown for {profile_url}")
                                return None
                    break
                except Exception as retry_error:
                    if attempt < max_retries - 1:
                        logging.warning(f"Retry {attempt + 1}/{max_retries} failed: {str(retry_error)}")
                        await page.wait_for_timeout(random.randint(2000, 4000))
                        continue
                    else:
                        raise retry_error
            
            logging.error(f"Could not find LinkedIn profile in Google search results: {profile_url}")
            return None
                
        except Exception as e:
            logging.error(f"Error searching and scraping profile {profile_url}: {str(e)}")
            return None

    async def scrape_profiles(self, search_query: str, max_profiles: int = 10):
        logging.info(f"Starting LinkedIn scraping for query: {search_query}")
        start_time = datetime.now()
        browser = None

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=False,
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
                    # Try to use existing cookies first
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
                        # Perform search using direct URL
                        encoded_query = urllib.parse.quote(search_query)
                        search_url = f'https://www.linkedin.com/search/results/people/?keywords={encoded_query}&origin=SWITCH_SEARCH_VERTICAL'
                        logging.info(f"Navigating to search URL: {search_url}")
                        
                        await page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
                        await page.wait_for_timeout(5000)  # Wait for content to load
                        
                        # Wait for search results container
                        await page.wait_for_selector('.search-results-container', timeout=30000)
                        
                        # Scroll to load all results
                        logging.info("Scrolling to load all results...")
                        await self.scroll_page(page)
                        
                        # Extract profile links using the specific class and structure
                        logging.info("Finding profile elements...")
                        # Get all profile elements
                        profile_elements = await page.query_selector_all('li.qSrOnTsMyRwSJdzfWtiXNDUSlIuhlSAwKBA')
                        logging.info(f"Found {len(profile_elements)} profile elements")
                        
                        # Keep track of processed URLs to avoid duplicates
                        processed_urls = set()
                        profiles_processed = 0
                        
                        for profile_elem in profile_elements[:max_profiles]:
                            try:
                                # Get the first anchor element with the specific class
                                anchor = await profile_elem.query_selector('a.PVVHCCBevdEmHKyAIeyIvuDqupzgfdjtlk[href*="/in/"]')
                                if not anchor:
                                    continue
                                
                                # Get the href attribute
                                profile_url = await anchor.get_attribute('href')
                                if not profile_url:
                                    logging.warning("No href found for profile element")
                                    continue
                                
                                # Clean the URL to get just the profile path
                                if '?' in profile_url:
                                    profile_url = profile_url.split('?')[0]
                                
                                # Skip if we've already processed this URL
                                if profile_url in processed_urls:
                                    logging.info(f"Skipping duplicate profile: {profile_url}")
                                    continue
                                
                                processed_urls.add(profile_url)
                                
                                # Get the name using JavaScript evaluation for better accuracy
                                name = await profile_elem.evaluate('''(element) => {
                                    const nameSpan = element.querySelector('.display-flex .aPuzKckRsIgPYKUzzqaMvfIPlKWzY span[dir="ltr"] span[aria-hidden="true"]');
                                    return nameSpan ? nameSpan.textContent.trim() : "Name not found";
                                }''')
                                
                                # Get designation if available
                                designation_elem = await profile_elem.evaluate('''(element) => {
                                    const container = element.closest("li");
                                    if (!container) return null;
                                    const designation = container.querySelector(".ekXvpNRCappdoRCJxXnFJSbMpPfQTfKqsaTO");
                                    return designation ? designation.textContent.trim() : null;
                                }''')
                                
                                # Get location if available
                                location_elem = await profile_elem.evaluate('''(element) => {
                                    const container = element.closest("li");
                                    if (!container) return null;
                                    const location = container.querySelector(".bMcLkQDJtqmcUNhrMfGmnjxUfcTfXT");
                                    return location ? location.textContent.trim() : null;
                                }''')
                                
                                logging.info(f"Found profile: {name} - {profile_url}")
                                
                                # Now search and scrape the complete profile
                                logging.info(f"Searching and scraping complete profile: {profile_url}")
                                # profile_markdown = await self.search_and_scrape_profile(page, profile_url)
                                
                                # Print the profile information
                                print(f"\nProfile {profiles_processed + 1}:")
                                print("=" * 40)
                                print(f"Name: {name}")
                                if designation_elem:
                                    print(f"Designation: {designation_elem}")
                                if location_elem:
                                    print(f"Location: {location_elem}")
                                print(f"LinkedIn URL: {profile_url}")
                                # if profile_markdown:
                                #     print("Profile markdown generated successfully")
                                # print("=" * 40)
                                
                                profiles_processed += 1
                                
                                # Add random delay between profiles
                                delay = random.uniform(1, 2)
                                await asyncio.sleep(delay)
                                
                            except Exception as e:
                                logging.error(f"Error processing profile element: {str(e)}")
                                continue
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
            
            # Wait for login form
            await page.wait_for_selector('#username', timeout=5000)
            await page.wait_for_selector('#password', timeout=5000)
            
            # Fill login form
            await page.fill('#username', 'anujpatil917@gmail.com')
            await page.fill('#password', 'Anuj@789@anuj')
            await page.click('button[type="submit"]')
            
            # Wait for navigation
            await page.wait_for_timeout(5000)
            
            # Check if login was successful
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
        await scraper.scrape_profiles("Sachin Raj", max_profiles=5)
    except Exception as e:
        logging.error(f"Fatal error in main: {str(e)}", exc_info=True)
    finally:
        logging.info("LinkedIn scraper finished")

if __name__ == "__main__":
    asyncio.run(main()) 