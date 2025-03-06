import asyncio
from playwright.async_api import async_playwright
import os
from pathlib import Path
import json
from datetime import datetime
import logging
import random

# Enhanced logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler("linkedin_scraper.log", mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Add a separator in log file for new runs
logging.info("\n" + "="*50 + "\nNEW SCRAPING SESSION STARTED\n" + "="*50)

class LinkedInProfileScraper:
    def __init__(self):
        logging.info("Initializing LinkedIn Profile Scraper...")
        self.user_data_dir = os.path.join(str(Path.home()), ".linkedin_automation")
        self.cookies_file = os.path.join(self.user_data_dir, "cookies.json")
        self.debug_dir = "debug_output"
        os.makedirs(self.debug_dir, exist_ok=True)
        logging.info(f"User data directory: {self.user_data_dir}")
        logging.info(f"Cookies file: {self.cookies_file}")
        logging.info(f"Debug directory: {self.debug_dir}")

    async def extract_profile_markdown(self, page, profile_url):
        """Extract detailed profile information and return as markdown."""
        try:
            logging.info(f"Starting extraction for profile: {profile_url}")
            await page.goto(profile_url)
            logging.info("Waiting for profile page to load...")
            await page.wait_for_timeout(3000)
            
            markdown = []
            
            # Extract basic info
            logging.info("Extracting basic information...")
            name = await page.evaluate('() => document.querySelector("h1")?.innerText || "Not Found"')
            headline = await page.evaluate('() => document.querySelector(".text-body-medium")?.innerText || "Not Found"')
            logging.info(f"Found profile: {name} - {headline}")
            
            markdown.append(f"# {name}")
            markdown.append(f"## {headline}\n")
            
            # About section
            logging.info("Extracting about section...")
            about = await page.evaluate('() => document.querySelector(".display-flex.ph5.pv3 .pv-shared-text-with-see-more span")?.innerText || ""')
            if about:
                logging.info("About section found")
                markdown.append("## About")
                markdown.append(about + "\n")
            else:
                logging.info("No about section found")
            
            # Experience
            logging.info("Extracting experience section...")
            exp_items = await page.evaluate('''
                () => {
                    const items = document.querySelectorAll('#experience-section .pv-entity__position-group');
                    return Array.from(items).map(item => {
                        const company = item.querySelector('.pv-entity__company-summary-info h3')?.innerText || '';
                        const title = item.querySelector('.pv-entity__summary-info h3')?.innerText || '';
                        const duration = item.querySelector('.pv-entity__date-range span:nth-child(2)')?.innerText || '';
                        return `- ${title} at ${company} (${duration})`;
                    });
                }
            ''')
            
            if exp_items and len(exp_items) > 0:
                logging.info(f"Found {len(exp_items)} experience items")
                markdown.append("## Experience")
                markdown.extend(exp_items)
                markdown.append("")
            else:
                logging.info("No experience items found")
            
            # Education
            logging.info("Extracting education section...")
            edu_items = await page.evaluate('''
                () => {
                    const items = document.querySelectorAll('#education-section .pv-education-entity');
                    return Array.from(items).map(item => {
                        const school = item.querySelector('h3')?.innerText || '';
                        const degree = item.querySelector('.pv-entity__degree-name .pv-entity__comma-item')?.innerText || '';
                        return `- ${degree} from ${school}`;
                    });
                }
            ''')
            
            if edu_items and len(edu_items) > 0:
                logging.info(f"Found {len(edu_items)} education items")
                markdown.append("## Education")
                markdown.extend(edu_items)
                markdown.append("")
            else:
                logging.info("No education items found")
            
            # Skills
            logging.info("Extracting skills section...")
            skills = await page.evaluate('''
                () => {
                    const items = document.querySelectorAll('.pv-skill-category-entity__name-text');
                    return Array.from(items).map(item => item.innerText);
                }
            ''')
            
            if skills and len(skills) > 0:
                logging.info(f"Found {len(skills)} skills")
                markdown.append("## Skills")
                markdown.extend([f"- {skill}" for skill in skills])
                markdown.append("")
            else:
                logging.info("No skills found")
            
            # Contact info
            logging.info("Adding contact information...")
            markdown.append("## Contact")
            markdown.append(f"- LinkedIn: {profile_url}")
            
            logging.info(f"Successfully extracted profile data for: {name}")
            return "\n".join(markdown)
            
        except Exception as e:
            logging.error(f"Error extracting profile info: {str(e)}", exc_info=True)
            return f"Error extracting profile: {str(e)}"

    async def perform_login(self, page):
        """Handle login process with cookie support."""
        logging.info("Starting login process...")
        
        if os.path.exists(self.cookies_file):
            logging.info("Found existing cookies file, attempting to use saved cookies...")
            try:
                with open(self.cookies_file, 'r') as f:
                    cookies = json.load(f)
                logging.info(f"Loaded {len(cookies)} cookies from file")
                await page.context.add_cookies(cookies)
                
                logging.info("Navigating to LinkedIn feed...")
                await page.goto('https://www.linkedin.com/feed/')
                await page.wait_for_timeout(5000)
                
                if 'feed' in page.url:
                    logging.info("Successfully logged in using cookies!")
                    return True
                else:
                    logging.warning("Cookie login failed - not on feed page")
                
            except Exception as e:
                logging.error(f"Error during cookie login: {str(e)}", exc_info=True)
                
        logging.info("Proceeding with manual login...")
        try:
            logging.info("Navigating to login page...")
            await page.goto('https://www.linkedin.com/login')
            await page.wait_for_timeout(3000)
            
            logging.info("Filling login form...")
            await page.fill('#username', 'anujpatil917@gmail.com')
            await page.fill('#password', 'Anuj@789@anuj')
            
            logging.info("Submitting login form...")
            await page.click('button[type="submit"]')
            await page.wait_for_timeout(5000)
            
            if 'feed' in page.url:
                logging.info("Successfully logged in manually!")
                
                logging.info("Saving cookies for future use...")
                cookies = await page.context.cookies()
                os.makedirs(self.user_data_dir, exist_ok=True)
                with open(self.cookies_file, 'w') as f:
                    json.dump(cookies, f)
                logging.info(f"Saved {len(cookies)} cookies to file")
                return True
            else:
                logging.warning("Manual login failed - not on feed page")
                
        except Exception as e:
            logging.error(f"Login failed: {str(e)}", exc_info=True)
            
        return False

    async def perform_search(self, page, search_query):
        """Perform search and return results."""
        try:
            logging.info(f"Starting search for query: '{search_query}'")
            encoded_query = search_query.replace(' ', '%20')
            search_url = f'https://www.linkedin.com/search/results/people/?keywords={encoded_query}'
            
            logging.info(f"Navigating to search URL: {search_url}")
            await page.goto(search_url)
            logging.info("Waiting for search results to load...")
            await page.wait_for_timeout(5000)
            
            logging.info("Extracting profile URLs from search results...")
            profile_urls = await page.evaluate('''
                () => {
                    const links = document.querySelectorAll('.entity-result__title-text a');
                    return Array.from(links).map(link => link.href).filter(url => url.includes('/in/'));
                }
            ''')
            
            logging.info(f"Found {len(profile_urls)} profile URLs")
            return profile_urls
            
        except Exception as e:
            logging.error(f"Error performing search: {str(e)}", exc_info=True)
            return []

    async def scrape_profiles(self, search_query, max_pages=3):
        logging.info(f"Starting profile scraping for query: '{search_query}' (max pages: {max_pages})")
        start_time = datetime.now()
        
        try:
            async with async_playwright() as p:
                logging.info("Launching browser...")
                browser = await p.chromium.launch(
                    headless=False,
                    args=['--disable-blink-features=AutomationControlled']
                )
                logging.info("Creating browser context...")
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0 Safari/537.36'
                )
                page = await context.new_page()
                
                if not await self.perform_login(page):
                    logging.error("Login failed, aborting scraping")
                    await browser.close()
                    return
                
                profile_urls = await self.perform_search(page, search_query)
                if not profile_urls:
                    logging.error("No profiles found, aborting scraping")
                    await browser.close()
                    return
                
                logging.info(f"Starting to process {len(profile_urls)} profiles...")
                
                # Extract and print markdown for each profile
                for i, profile_url in enumerate(profile_urls, 1):
                    logging.info(f"Processing profile {i}/{len(profile_urls)}: {profile_url}")
                    markdown = await self.extract_profile_markdown(page, profile_url)
                    print(f"\nProfile {i}/{len(profile_urls)}:\n")
                    print(markdown)
                    print("\n" + "="*80 + "\n")
                    
                    delay = random.randint(3000, 5000)
                    logging.info(f"Waiting {delay}ms before next profile...")
                    await page.wait_for_timeout(delay)
                
                logging.info("Closing browser...")
                await browser.close()
                
                end_time = datetime.now()
                duration = end_time - start_time
                logging.info(f"Scraping completed in {duration.total_seconds():.2f} seconds")
                logging.info(f"Successfully processed {len(profile_urls)} profiles")
                
        except Exception as e:
            logging.error(f"Unexpected error during scraping: {str(e)}", exc_info=True)

async def main():
    logging.info("Starting LinkedIn Profile Scraper...")
    try:
        scraper = LinkedInProfileScraper()
        await scraper.scrape_profiles("Sachin Raj", max_pages=3)
    except Exception as e:
        logging.error(f"Fatal error in main: {str(e)}", exc_info=True)
    finally:
        logging.info("LinkedIn Profile Scraper finished")

if __name__ == "__main__":
    asyncio.run(main()) 