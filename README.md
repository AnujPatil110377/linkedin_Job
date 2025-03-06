# LinkedIn Automation Scraper

This project automates the process of scraping job postings (and optionally profiles) from LinkedIn using Playwright. It supports cookie-based login persistence, scrolling to load dynamic content, and concurrent extraction of job data.

## Overview

The main functionality is implemented in the file [D:/xbox/linkedin_jobs.py](D:/xbox/linkedin_jobs.py), which provides the following features:

- **Cookie Management:** Automatically loads and saves cookies to bypass repeated logins.
- **Login Automation:** Uses automated login if no valid cookies are available.
- **Dynamic Content Loading:** Scrolls the page to load all available job postings.
- **Job Data Extraction:** Extracts job title, company, location, application insights, and additional metadata.
- **Concurrent Processing:** Processes job listings in batches to improve performance.
- **Logging:** Detailed logging of all steps to assist with debugging and monitoring.

## Prerequisites

- Python 3.7+
- [Playwright for Python](https://playwright.dev/python/)
- A valid LinkedIn account for scraping (credentials are used in the source code)

## Setup and Usage

1. **Install Dependencies:**

   ```sh
   pip install playwright
   playwright install
