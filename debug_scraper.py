import asyncio
from playwright.async_api import async_playwright
import os
from pathlib import Path
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def debug_scrape():
    # Setup directories
    user_data_dir = os.path.join(str(Path.home()), ".linkedin_automation")
    cookies_file = os.path.join(user_data_dir, "cookies.json")
    debug_dir = "debug_output"
    os.makedirs(debug_dir, exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]
        )
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0 Safari/537.36'
        )
        
        page = await context.new_page()
        
        # Try to load existing cookies first
        if os.path.exists(cookies_file):
            logging.info("Found existing cookies, attempting to use them...")
            with open(cookies_file, 'r') as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
            
            # Try to access feed directly
            await page.goto('https://www.linkedin.com/feed/')
            await page.wait_for_load_state('networkidle')
            
            # Save feed page HTML for debugging
            feed_html = await page.content()
            with open(os.path.join(debug_dir, "feed_page.html"), "w", encoding="utf-8") as f:
                f.write(feed_html)
            
            if 'feed' in page.url:
                logging.info("Successfully logged in using cookies!")
            else:
                logging.info("Cookie login failed, proceeding with manual login...")
                await perform_manual_login(page, user_data_dir, cookies_file)
        else:
            logging.info("No cookies found, proceeding with manual login...")
            await perform_manual_login(page, user_data_dir, cookies_file)
        
        # Now that we're logged in, let's debug the search functionality
        search_query = "Sachin Raj"
        encoded_query = search_query.replace(' ', '%20')
        search_url = f'https://www.linkedin.com/search/results/people/?keywords={encoded_query}&page=1'
        
        logging.info(f"Navigating to search URL: {search_url}")
        await page.goto(search_url)
        await page.wait_for_load_state('networkidle')
        
        # Take screenshot of search results
        await page.screenshot(path=os.path.join(debug_dir, "search_results.png"), full_page=True)
        
        # Save search page HTML
        search_html = await page.content()
        with open(os.path.join(debug_dir, "search_results.html"), "w", encoding="utf-8") as f:
            f.write(search_html)
        
        # Debug search results
        logging.info("\nDebugging search results...")
        
        # Try different selectors and log results
        selectors_to_check = [
            '.search-results-container',
            '.reusable-search__result-container',
            '.entity-result',
            'li.reusable-search__result-container',
            '.entity-result__item',
            '.search-results__list'
        ]
        
        for selector in selectors_to_check:
            try:
                elements = await page.query_selector_all(selector)
                logging.info(f"Selector '{selector}': found {len(elements)} elements")
                
                if elements:
                    first_elem = elements[0]
                    # Try to extract profile info from first element
                    try:
                        name_elem = await first_elem.query_selector('.entity-result__title-text a')
                        if name_elem:
                            name = await name_elem.inner_text()
                            url = await name_elem.get_attribute('href')
                            logging.info(f"First result - Name: {name}, URL: {url}")
                    except Exception as e:
                        logging.error(f"Error extracting info from element: {str(e)}")
            except Exception as e:
                logging.error(f"Error checking selector {selector}: {str(e)}")
        
        # Check for profile links
        profile_links = await page.query_selector_all('a[href*="/in/"]')
        logging.info(f"\nFound {len(profile_links)} profile links")
        
        # Save current page state
        logging.info(f"Current URL: {page.url}")
        
        # Check for any error messages
        error_msgs = await page.query_selector_all('.error-message, .alert, .notification')
        if error_msgs:
            logging.info("\nFound error messages:")
            for msg in error_msgs:
                text = await msg.inner_text()
                logging.info(text)
        
        input("\nPress Enter to close the browser...")
        await browser.close()

async def perform_manual_login(page, user_data_dir, cookies_file):
    """Handle manual login process and save cookies."""
    await page.goto('https://www.linkedin.com/login')
    await page.wait_for_load_state('networkidle')
    
    # Fill login form
    await page.fill('#username', 'anujpatil917@gmail.com')
    await page.fill('#password', 'Anuj@789@anuj')
    
    # Click login button
    await page.click('button[type="submit"]')
    await page.wait_for_load_state('networkidle')
    
    # Wait for navigation to complete
    try:
        await page.wait_for_url(lambda url: 'feed' in url, timeout=30000)
        logging.info("Successfully logged in manually!")
        
        # Save cookies for future use
        cookies = await page.context.cookies()
        os.makedirs(user_data_dir, exist_ok=True)
        with open(cookies_file, 'w') as f:
            json.dump(cookies, f)
        logging.info("Saved cookies for future use")
    except Exception as e:
        logging.error(f"Error during login: {str(e)}")

if __name__ == "__main__":
    asyncio.run(debug_scrape()) 