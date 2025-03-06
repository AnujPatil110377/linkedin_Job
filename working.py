import asyncio
from crawl4ai import *
import re
from dataclasses import dataclass
from typing import List

@dataclass
class LinkedInProfile:
    name: str
    designation: str
    url: str
    description: str = ""
    connections: str = "Not specified"

def extract_linkedin_profiles(markdown_content: str) -> List[LinkedInProfile]:
    profiles = []
    
    # Pattern to match LinkedIn profile sections
    profile_pattern = r'\[([^\]]+)\]\(https://www\.bing\.com/<(https:/[^>]+)>\)\n## \[([^\]]+)\]'
    matches = re.finditer(profile_pattern, markdown_content)
    
    for match in matches:
        if 'linkedin.com/in/' not in match.group(2):
            continue
            
        # Clean up the URL (remove bing redirect)
        url = match.group(2).replace('https://', 'https://')
        
        # Extract name and designation
        title_parts = match.group(3).split(' - ')
        name = title_parts[0].strip('*')
        designation = 'HR at Amazon'  # Default
        if len(title_parts) > 1:
            designation = title_parts[1].strip('*')
            
        # Find description in the following lines
        description = ""
        desc_start = markdown_content.find(match.group(0)) + len(match.group(0))
        next_section = markdown_content.find('[', desc_start)
        if next_section != -1:
            description = markdown_content[desc_start:next_section].strip()
        
        # Extract connections if available
        connections = "Not specified"
        if "connections" in description:
            conn_match = re.search(r'(\d+)\+?\s*connections', description)
            if conn_match:
                connections = f"{conn_match.group(1)}+"
        
        profile = LinkedInProfile(
            name=name,
            designation=designation,
            url=url,
            description=description,
            connections=connections
        )
        profiles.append(profile)
    
    return profiles

async def main():
    async with AsyncWebCrawler() as crawler:
        # List of pages to crawl (1-3)
        pages = [1, 11, 21]  # First three pages
        all_profiles = []
        
        for start_index in pages:
            urls = [f"https://www.bing.com/search?q=hr+amazon+linkedin&first={start_index}",
                    f"https://www.bing.com/search?q=hr+google+linkedin&first={start_index}",
                    f"https://www.bing.com/search?q=hr+microsoft+linkedin&first={start_index}",
                    f"https://www.bing.com/search?q=hr+apple+linkedin&first={start_index}"]
            for url in urls:
                result = await crawler.arun(url=url)
                
            # Extract profiles from this page
                profiles = extract_linkedin_profiles(result.markdown)
                all_profiles.extend(profiles)
            
            # Wait a bit between requests to be polite
                await asyncio.sleep(2)
        
        # Print the results in a formatted way
            print("\n=== LinkedIn Profiles Found ===\n")
            for i, profile in enumerate(all_profiles, 1):
                print(f"Profile {i}:")
                print(f"Name: {profile.name}")
                print(f"Designation: {profile.designation}")
                print(f"LinkedIn URL: {profile.url}")
                print(f"Connections: {profile.connections}")
                if profile.description:
                    print(f"Description: {profile.description.strip()}")
                print("-" * 50)
            
            print(f"\nTotal profiles found: {len(all_profiles)}")

if __name__ == "__main__":
    asyncio.run(main())