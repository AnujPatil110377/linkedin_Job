import asyncio
from crawl4ai import *
import re
from dataclasses import dataclass
from typing import List
import psutil
import csv
from datetime import datetime
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("profile_scraper.log", mode='a'),
        logging.StreamHandler()
    ]
)

@dataclass
class LinkedInProfile:
    name: str
    designation: str
    url: str
    description: str = ""
    connections: str = "Not specified"
    company: str = "Not specified"

def save_profiles_to_csv(profiles: List[LinkedInProfile], search_query: str):
    """Save profiles to a CSV file with timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"linkedin_profiles_{timestamp}.csv"
    
    # Create 'output' directory if it doesn't exist
    os.makedirs('output', exist_ok=True)
    filepath = os.path.join('output', filename)
    
    print(f"\nSaving profiles to: {filepath}")
    
    with open(filepath, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        # Write header
        writer.writerow(['Name', 'Designation', 'Company', 'Connections', 'LinkedIn URL', 'Description', 'Search Query'])
        
        # Write profile data
        for profile in profiles:
            # Extract company from designation if possible
            company = profile.company
            if 'at ' in profile.designation.lower():
                company = profile.designation.lower().split('at ')[-1].strip().title()
            
            writer.writerow([
                profile.name,
                profile.designation,
                company,
                profile.connections,
                profile.url,
                profile.description.replace('\n', ' '),
                search_query
            ])
    
    print(f"Saved {len(profiles)} profiles to CSV file")

def extract_linkedin_profiles(markdown_content: str, search_query: str) -> List[LinkedInProfile]:
    profiles = []
    logging.debug(f"Processing markdown content length: {len(markdown_content)}")
    
    try:
        # Pattern to match LinkedIn profile sections
        profile_pattern = r'\[([^\]]+)\]\(https://www\.bing\.com/<(https:/[^>]+)>\)\n## \[([^\]]+)\]'
        matches = re.finditer(profile_pattern, markdown_content)
        
        for match in matches:
            if 'linkedin.com/in/' not in match.group(2):
                continue
                
            # Clean up the URL (remove bing redirect)
            url = match.group(2).replace('https://', 'https://')
            logging.debug(f"Found LinkedIn URL: {url}")
            
            # Extract name and designation
            title_parts = match.group(3).split(' - ')
            name = title_parts[0].strip('*')
            designation = 'HR Professional'  # Default
            company = "Not specified"
            
            if len(title_parts) > 1:
                designation = title_parts[1].strip('*')
                # Try to extract company
                if ' at ' in designation.lower():
                    company = designation.split(' at ')[-1].strip()
                elif ' @ ' in designation:
                    company = designation.split(' @ ')[-1].strip()
            
            # Find description in the following lines
            description = ""
            desc_start = markdown_content.find(match.group(0)) + len(match.group(0))
            next_section = markdown_content.find('[', desc_start)
            if next_section != -1:
                description = markdown_content[desc_start:next_section].strip()
            
            # Extract connections if available
            connections = "Not specified"
            if "connections" in description.lower():
                conn_match = re.search(r'(\d+)\+?\s*connections', description, re.IGNORECASE)
                if conn_match:
                    connections = f"{conn_match.group(1)}+"
            
            profile = LinkedInProfile(
                name=name,
                designation=designation,
                url=url,
                description=description,
                connections=connections,
                company=company
            )
            
            logging.debug(f"Extracted profile: {name} - {company}")
            profiles.append(profile)
            
    except Exception as e:
        logging.error(f"Error extracting profiles: {str(e)}", exc_info=True)
    
    logging.info(f"Total profiles extracted: {len(profiles)}")
    return profiles

async def crawl_parallel(urls: List[str], max_concurrent: int = 3):
    process = psutil.Process()
    peak_memory = 0
    all_profiles = []  # Store all profiles across all searches

    def log_memory(prefix=""):
        nonlocal peak_memory
        current_mem = process.memory_info().rss
        peak_memory = max(peak_memory, current_mem)
        print(f"{prefix}Memory Usage: {current_mem // (1024 * 1024)} MB, Peak: {peak_memory // (1024 * 1024)} MB")

    browser_config = BrowserConfig(
        headless=False,  # Set to False to see what's happening
        verbose=True,
        use_managed_browser=True,
        browser_type="chromium",
        extra_args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--no-sandbox"
        ]
    )
    
    # Create crawler with default config
    default_config = CrawlerRunConfig(
        markdown_generator=DefaultMarkdownGenerator(),
        wait_until='networkidle',
        page_timeout=30000
    )
    
    crawler = AsyncWebCrawler(
        browser_config=browser_config,
        default_run_config=default_config
    )
    await crawler.start()

    try:
        for i in range(0, len(urls), max_concurrent):
            batch = urls[i:i + max_concurrent]
            tasks = []
            
            for j, url in enumerate(batch):
                session_id = f"profile_session_{i + j}"
                task = crawler.arun(
                    url=url,
                    config=CrawlerRunConfig(
                        markdown_generator=DefaultMarkdownGenerator(),
                        wait_until='networkidle'
                    ),
                    session_id=session_id
                )
                tasks.append(task)

            log_memory(f"Before batch {i // max_concurrent + 1}: ")
            results = await asyncio.gather(*tasks, return_exceptions=True)
            log_memory(f"After batch {i // max_concurrent + 1}: ")

            for url, result in zip(batch, results):
                if isinstance(result, Exception):
                    logging.error(f"Error crawling {url}: {result}")
                    print(f"Error crawling {url}: {result}")
                elif result.success:
                    print(f"Successfully crawled: {url}")
                    # Extract search query from URL
                    search_query = re.search(r'q=hr\+([^+]+)\+linkedin', url).group(1).replace('+', ' ').title()
                    
                    # Extract profiles from markdown
                    profiles = extract_linkedin_profiles(result.markdown, search_query)
                    
                    # Print found profiles
                    for profile in profiles:
                        print(f"\nFound profile:")
                        print(f"Name: {profile.name}")
                        print(f"Designation: {profile.designation}")
                        print(f"Company: {profile.company}")
                        print(f"URL: {profile.url}")
                        print(f"Connections: {profile.connections}")
                        print("-" * 40)
                    
                    all_profiles.extend(profiles)
                    print(f"Extracted {len(profiles)} profiles from this page")
                else:
                    logging.error(f"Failed to crawl: {url}")
                    print(f"Failed to crawl: {url}")

            # Save batch results to CSV
            if all_profiles:
                save_profiles_to_csv(all_profiles, "Multiple Companies HR Search")
            
            # Add delay between batches
            await asyncio.sleep(2)

    finally:
        await crawler.close()
        print(f"Peak memory usage (MB): {peak_memory // (1024 * 1024)}")
        print(f"Total profiles found: {len(all_profiles)}")

async def main():
    urls = [
        "https://www.bing.com/search?q=hr+amazon+linkedin+site:linkedin.com/in/&first=1",
        "https://www.bing.com/search?q=hr+amazon+linkedin+site:linkedin.com/in/&first=11",
        "https://www.bing.com/search?q=hr+amazon+linkedin+site:linkedin.com/in/&first=21",
        "https://www.bing.com/search?q=hr+google+linkedin+site:linkedin.com/in/&first=1",
        "https://www.bing.com/search?q=hr+google+linkedin+site:linkedin.com/in/&first=11",
        "https://www.bing.com/search?q=hr+google+linkedin+site:linkedin.com/in/&first=21",
        "https://www.bing.com/search?q=hr+microsoft+linkedin+site:linkedin.com/in/&first=1",
        "https://www.bing.com/search?q=hr+microsoft+linkedin+site:linkedin.com/in/&first=11",
        "https://www.bing.com/search?q=hr+microsoft+linkedin+site:linkedin.com/in/&first=21",
        "https://www.bing.com/search?q=hr+apple+linkedin+site:linkedin.com/in/&first=1",
        "https://www.bing.com/search?q=hr+apple+linkedin+site:linkedin.com/in/&first=11",
        "https://www.bing.com/search?q=hr+apple+linkedin+site:linkedin.com/in/&first=21"
    ]
    await crawl_parallel(urls, max_concurrent=4)

if __name__ == "__main__":
    asyncio.run(main())
