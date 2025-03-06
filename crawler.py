import asyncio
import logging
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("crawler_debug.log", mode='a'),
        logging.StreamHandler()
    ]
)

async def check_login_status(crawler):
    """Check if we're logged in by visiting LinkedIn."""
    try:
        result = await crawler.arun(
            url='https://www.linkedin.com/feed/',
            config=CrawlerRunConfig(
                markdown_generator=DefaultMarkdownGenerator(),
                js_code='''
                // Wait for either feed content or login form
                try {
                    await Promise.race([
                        page.waitForSelector('.feed-shared-update-v2', { timeout: 5000 }),
                        page.waitForSelector('#username', { timeout: 5000 })
                    ]);
                    
                    // Check if we're on the login page
                    const isLoginPage = await page.evaluate(() => {
                        return !!document.querySelector('#username');
                    });
                    
                    return { isLoggedIn: !isLoginPage };
                } catch (e) {
                    return { isLoggedIn: false, error: e.message };
                }
                '''
            )
        )
        
        is_logged_in = result.success and result.metadata.get('isLoggedIn', False)
        if is_logged_in:
            logging.info("Already logged in")
        else:
            logging.info("Not logged in")
        return is_logged_in
        
    except Exception as e:
        logging.error(f"Error checking login status: {str(e)}")
        return False

async def perform_login(crawler):
    """Handle the login process."""
    try:
        logging.info("Attempting login...")
        
        result = await crawler.arun(
            url='https://www.linkedin.com/login',
            config=CrawlerRunConfig(
                markdown_generator=DefaultMarkdownGenerator(),
                js_code='''
                try {
                    // Wait for form elements with longer timeout
                    await page.waitForSelector('input[name="session_key"]', { timeout: 10000 });
                    await page.waitForSelector('input[name="session_password"]', { timeout: 10000 });
                    
                    // Clear and fill login form
                    await page.evaluate(() => {
                        document.querySelector('input[name="session_key"]').value = '';
                        document.querySelector('input[name="session_password"]').value = '';
                    });
                    
                    // Type credentials with delay
                    await page.type('input[name="session_key"]', 'anujpatil917@gmail.com', { delay: 100 });
                    await page.type('input[name="session_password"]', 'Anuj@789@anuj', { delay: 100 });
                    
                    // Click sign in button
                    await page.click('button[type="submit"]');
                    
                    // Wait for navigation to complete
                    await page.waitForNavigation({ waitUntil: 'networkidle0', timeout: 30000 });
                    
                    // Wait a bit for any redirects
                    await page.waitForTimeout(3000);
                    
                    // Check if we're successfully logged in
                    const currentUrl = await page.url();
                    const isLoggedIn = currentUrl.includes('/feed/') || 
                                     currentUrl.includes('/mynetwork/') ||
                                     await page.evaluate(() => {
                                         return !!document.querySelector('.feed-identity-module');
                                     });
                    
                    logging.debug(`Current URL after login: ${currentUrl}`);
                    logging.debug(`Login check result: ${isLoggedIn}`);
                    
                    return { success: isLoggedIn };
                } catch (e) {
                    logging.error(`Login error: ${e.message}`);
                    return { success: false, error: e.message };
                }
                '''
            )
        )
        
        if result.success and result.metadata.get('success', False):
            logging.info("Login successful")
            return True
        else:
            error_msg = result.metadata.get('error', 'Unknown error')
            logging.error(f"Login failed: {error_msg}")
            return False
        
    except Exception as e:
        logging.error(f"Error during login: {str(e)}")
        return False

async def main():
    logging.info("Starting crawler script...")
    
    # 1) Reference your persistent data directory
    logging.debug("Configuring browser with persistent data directory...")
    browser_config = BrowserConfig(
        headless=False,
        verbose=True,
        use_managed_browser=True,
        browser_type="chromium",
        user_data_dir="C:/Users/91798/chrome_crawler_profile"
    )
    logging.debug(f"Browser config created: {browser_config}")

    # 2) Create default run config
    logging.debug("Creating default run configuration...")
    default_run_config = CrawlerRunConfig(
        markdown_generator=DefaultMarkdownGenerator(),
        wait_until='networkidle',
        page_timeout=30000
    )
    logging.debug(f"Default run config created: {default_run_config}")

    # 3) Create search-specific config
    logging.debug("Creating search-specific configuration...")
    search_config = CrawlerRunConfig(
        markdown_generator=DefaultMarkdownGenerator(),
        wait_for=".search-results-container",
        js_code='''
        // Wait for results to load
        await page.waitForSelector('.search-results-container', { timeout: 10000 });
        
        // Scroll to load more results
        let prevHeight = 0;
        let newHeight = await page.evaluate(() => document.body.scrollHeight);
        
        while (prevHeight !== newHeight) {
            prevHeight = newHeight;
            await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
            await page.waitForTimeout(2000);
            newHeight = await page.evaluate(() => document.body.scrollHeight);
        }
        
        // Extract profile information
        const profiles = await page.evaluate(() => {
            const results = [];
            const cards = document.querySelectorAll('.reusable-search__result-container');
            
            cards.forEach(card => {
                const nameEl = card.querySelector('.app-aware-link');
                const titleEl = card.querySelector('.entity-result__primary-subtitle');
                const locationEl = card.querySelector('.entity-result__secondary-subtitle');
                
                if (nameEl) {
                    results.push({
                        name: nameEl.innerText.trim(),
                        url: nameEl.href,
                        title: titleEl ? titleEl.innerText.trim() : '',
                        location: locationEl ? locationEl.innerText.trim() : ''
                    });
                }
            });
            
            return { profiles: results };
        });
        
        return profiles;
        '''
    )
    logging.debug(f"Search config created: {search_config}")

    logging.info("Initializing crawler...")
    try:
        # Initialize crawler with default run config
        crawler = AsyncWebCrawler(
            browser_config=browser_config,
            default_run_config=default_run_config
        )
        await crawler.start()
        logging.info("Crawler initialized successfully")

        try:
            # Check login status and login if needed
            if not await check_login_status(crawler):
                if not await perform_login(crawler):
                    logging.error("Failed to log in to LinkedIn")
                    return
                logging.info("Successfully logged in to LinkedIn")

            # Now perform the search
            logging.debug("Attempting to access LinkedIn search URL...")
            result = await crawler.arun(
                url="https://www.linkedin.com/search/results/people/?keywords=Sachin%20Raj",
                config=search_config
            )
            
            logging.debug(f"Crawler result: success={result.success}")
            if result.success:
                logging.info("Successfully accessed search results!")
                logging.debug("Response metadata:")
                logging.debug(f"URL: {result.url}")
                logging.debug(f"HTML length: {len(result.html) if result.html else 0}")
                logging.debug(f"Markdown length: {len(result.markdown) if result.markdown else 0}")
                
                if result.metadata and 'profiles' in result.metadata:
                    profiles = result.metadata['profiles']
                    logging.info(f"Found {len(profiles)} profiles")
                    for i, profile in enumerate(profiles, 1):
                        print(f"\nProfile {i}:")
                        print(f"Name: {profile['name']}")
                        print(f"Title: {profile['title']}")
                        print(f"Location: {profile['location']}")
                        print(f"URL: {profile['url']}")
                        print("-" * 40)
                else:
                    logging.warning("No profiles found in search results")
            else:
                logging.error(f"Error: {result.error_message}")
                if hasattr(result, 'metadata'):
                    logging.debug(f"Result metadata: {result.metadata}")
        finally:
            await crawler.close()
            
    except Exception as e:
        logging.exception(f"An error occurred during crawling: {str(e)}")
    finally:
        logging.info("Crawler script finished")

if __name__ == "__main__":
    asyncio.run(main())