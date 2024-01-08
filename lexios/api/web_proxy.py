# proxy_link_data.py

import os
import requests
import uuid
import json
import asyncio
import threading

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor

from fastapi import BackgroundTasks

from admin.verify_folder import find_project_folder
from lexios.settings.main import DOWNLOAD_FOLDER
from lexios.database.users import retrieve_category_content, create_user_specific_data, update_user_specific_data
from lexios.database.models import UserSpecificData
from lexios.core.logger import CustomLogger

background_tasks = BackgroundTasks()

# Define a constant for internal system elements
SYSTEM = 1

# Restore stored cache or create a new one

# Retrieve cache if any
link_cache_data = retrieve_category_content(user_id=SYSTEM, data_category="link_cache")

if link_cache_data:
    # Decode the content from the JSON
    _cache = json.loads(link_cache_data[0].data_content)

    # Memory id for the cache
    cache_data_id = link_cache_data[0].data_id
else:
    _cache = {}
    # Will be initiated on the first update
    cache_data_id = None

# cache for url content, for now just for in-memory:
_cache_content = {}

# Define a lock
cache_lock = threading.Lock()

def update_cache_in_db():

    global cache_data_id

    # Acquire the lock
    cache_lock.acquire()

    try:
        # Cache already loaded
        if cache_data_id:
            # Update cache
            update_user_specific_data(user_id=SYSTEM,
                                      data_id=cache_data_id,
                                      new_data={'data_content': json.dumps(_cache)},
            )
            return
        else:
            # Setup for the first time
            try:
                # Generate a data_id
                new_data_id = str(uuid.uuid4())

                # Save in the database
                create_user_specific_data(UserSpecificData(
                    data_id=new_data_id,
                    user_id=SYSTEM,
                    data_category="link_cache",
                    data_content=json.dumps(_cache),
                ))

                # Register the data id for the next executions
                cache_data_id = new_data_id

            except Exception as e:
                with CustomLogger("lexios") as log:
                    log.error(f"Error when loading web_proxy cache. Details: {e}")

    finally:
        # Release the lock in a finally block to ensure it's released even if an exception occurs
        cache_lock.release()
    

async def get_link_icon_and_title(url, preferred_size=(120, 120)):
    try:

        # First check the cache 
        if _cache.get(url):
            return _cache.get(url)

        # Set up Chrome options
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # Run Chrome in headless mode

        # Initialize the WebDriver
        driver = webdriver.Chrome(options=chrome_options)

        # Load the webpage
        driver.get(url)

        # Wait for some time to let the page load (you may need to adjust this based on your needs)
        driver.implicitly_wait(5)

        # Get page source after waiting
        page_source = driver.page_source

        # Close the WebDriver
        driver.quit()

        # Parse the page source with BeautifulSoup
        soup = BeautifulSoup(page_source, 'html.parser')

        # Find apple-touch-icon with preferred size
        apple_touch_icon = soup.find('link', rel='apple-touch-icon', sizes=f'{preferred_size[0]}x{preferred_size[1]}')
        icon_url = urljoin(url, apple_touch_icon.get('href')) if apple_touch_icon else None

        # Find icon with preferred size
        icon = soup.find('link', rel='icon', sizes=f'{preferred_size[0]}x{preferred_size[1]}')
        icon_url = urljoin(url, icon.get('href')) if icon else icon_url

        # If preferred size not found, get any available icon
        any_icon = soup.find('link', rel='apple-touch-icon') or soup.find('link', rel='icon')
        icon_url = urljoin(url, any_icon.get('href')) if any_icon and not icon_url else icon_url

        # Get title
        title = soup.title.text.strip() if soup.title else None

        # Download the image content
        if icon_url:
            image_response = requests.get(icon_url)
            image_content = image_response.content

            # Extract the filename from the URL
            image_filename = os.path.basename(icon_url)

            project_folder = find_project_folder() or ""

            DOWNLOADS = os.path.join(project_folder, DOWNLOAD_FOLDER)

            #Make sure the folder exists
            os.makedirs(DOWNLOADS, exist_ok=True)

            image_path = os.path.join(DOWNLOADS, image_filename)  # Save in a 'static' folder

            # Save the image locally (optional)
            with open(image_path, 'wb') as f:
                f.write(image_content)

            # Return the image URL
            image_url = f'/downloads/{image_filename}'  # Adjust the path based on your server setup

            # Save results in cache to speed up next search
            data = {
                'icon_url': icon_url, 
                'title': title, 
                'image_url': image_url
                }
            
            _cache[url] = data
        
            # Trigger the extraction of the article content asynchronously
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, extract_visible_text_with_links, page_source, url)

            return data

        return {'icon_url': None, 'title': title}
    except Exception as e:
        return {'error': str(e)}


def extract_visible_text_with_links(page_source, base_url):
    try:
        # Parse the page source with BeautifulSoup
        soup = BeautifulSoup(page_source, 'html.parser')

        # Extract relevant text content along with corresponding URL links
        text_content = ""
        unique_urls = set()

        for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p']):
            text = element.get_text(strip=True)

            # Append text to text_content
            text_content += f"{text}\n"

            # Extract unique URLs
            urls = {urljoin(base_url, a['href']) for a in element.find_all('a', href=True)}
            unique_urls.update(urls)

        text_content = text_content.strip()
        href_index = list(unique_urls)

        # Create data structure
        data = {
            'text_content' : text_content,
            'href-index' : href_index,
        }

        # Update caches
        # Wildcard cache goes to DB
        update_cache_in_db()

        # Stripped content remains in-memory just in case
        _cache_content[base_url] = data
        
        return 
    
    except Exception as e:
        print(f"Error in extract_visible_text_with_links: {e}")
        return None



if __name__ == "__main__":
    # Example usage
    result = get_link_icon_and_title('https://www.reddit.com/r/reactjs/comments/irk6yq/how_to_fetch_image_title_etc_from_urls_and/?rdt=34312')
    print(result)
