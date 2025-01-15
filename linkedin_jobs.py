import asyncio
import os
from pathlib import Path
import json
import logging
from datetime import datetime
from playwright.async_api import async_playwright
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler("linkedin_jobs.log", mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class LinkedInJobScraper:
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

    async def extract_job_info(self, job_elem):
        """Extract job information from a job card."""
        try:
            job_data = await job_elem.evaluate('''(element) => {
                const data = {};
                
                // Get job title (fix duplicate title issue)
                const titleElem = element.querySelector('a.job-card-list__title--link strong');
                data.title = titleElem ? titleElem.textContent.trim() : null;
                data.job_link = titleElem ? titleElem.closest('a').href : null;
                
                // Get company name and logo
                const companyElem = element.querySelector('.artdeco-entity-lockup__subtitle');
                data.company = companyElem ? companyElem.textContent.trim() : null;
                
                const companyLogo = element.querySelector('.job-card-list__logo img');
                data.company_logo = companyLogo ? companyLogo.src : null;
                
                // Get location
                const locationElem = element.querySelector('.job-card-container__metadata-wrapper li');
                data.location = locationElem ? locationElem.textContent.trim() : null;
                
                // Get application insights
                const insightElem = element.querySelector('.job-card-container__job-insight-text');
                data.insight = insightElem ? insightElem.textContent.trim() : null;
                
                // Get footer information
                const footerItems = element.querySelectorAll('.job-card-list__footer-wrapper li');
                footerItems.forEach(item => {
                    if (item.textContent.includes('Easy Apply')) {
                        data.easy_apply = true;
                    }
                    if (item.classList.contains('job-card-container__footer-job-state')) {
                        data.status = item.textContent.trim();
                    }
                });
                
                // Get tracking ID
                const trackingId = titleElem ? titleElem.closest('a').getAttribute('data-control-id') : null;
                data.tracking_id = trackingId;
                
                return data;
            }''')
            return job_data
        except Exception as e:
            logging.error(f"Error extracting job info: {str(e)}")
            return None

    async def print_job_info(self, job_data, idx):
        """Print formatted job information."""
        if not job_data:
            return
            
        print(f"\nJob {idx}:")
        print("=" * 60)
        print(f"Title: {job_data['title']}")
        if job_data['company']:
            print(f"Company: {job_data['company']}")
        if job_data['location']:
            print(f"Location: {job_data['location']}")
        if job_data['insight']:
            print(f"Insight: {job_data['insight']}")
        if job_data.get('status'):
            print(f"Status: {job_data['status']}")
        if job_data.get('easy_apply'):
            print("Application: Easy Apply")
        print(f"Job Link: {job_data['job_link']}")
        if job_data['company_logo']:
            print(f"Company Logo: {job_data['company_logo']}")
        print("=" * 60)

    async def scrape_jobs(self, job_url: str):
        """Scrape jobs from LinkedIn jobs page."""
        logging.info(f"Starting LinkedIn job scraping")
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
                        logging.info(f"Navigating to jobs URL: {job_url}")
                        await page.goto(job_url, wait_until='domcontentloaded', timeout=30000)
                        await page.wait_for_timeout(2000)
                        
                        logging.info("Scrolling to load all job listings...")
                        await self.scroll_page(page)
                        
                        logging.info("Finding job elements...")
                        job_elements = await page.query_selector_all('.job-card-list__entity-lockup')
                        logging.info(f"Found {len(job_elements)} job listings")
                        
                        # Process jobs in batches
                        batch_size = 5
                        for i in range(0, len(job_elements), batch_size):
                            batch = job_elements[i:i + batch_size]
                            
                            # Extract job information concurrently
                            tasks = [self.extract_job_info(elem) for elem in batch]
                            jobs_data = await asyncio.gather(*tasks)
                            
                            for idx, job_data in enumerate(jobs_data, i + 1):
                                if not job_data:
                                    continue
                                
                                await self.print_job_info(job_data, idx)
                            
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
    logging.info("\n" + "="*50 + "\nNEW JOB SCRAPING SESSION STARTED\n" + "="*50)
    
    job_url = "https://www.linkedin.com/jobs/search/?currentJobId=4125128123&f_E=1&f_TPR=r7200&geoId=102713980&keywords=software%20engineer%20intern&origin=JOB_SEARCH_PAGE_JOB_FILTER&refresh=true&sortBy=DD"
    
    try:
        scraper = LinkedInJobScraper()
        await scraper.scrape_jobs(job_url)
    except Exception as e:
        logging.error(f"Fatal error in main: {str(e)}", exc_info=True)
    finally:
        loop = asyncio.get_event_loop()
        await loop.shutdown_asyncgens()
        
if __name__ == "__main__":
    asyncio.run(main()) 