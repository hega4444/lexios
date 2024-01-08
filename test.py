import os
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from admin.verify_folder import find_project_folder
from lexios.settings.main import DOWNLOAD_FOLDER

def get_link_icon_and_title(url, preferred_size=(120, 120)):
    try:
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

            # Save the image locally
            image_filename = 'icon.png'

            project_folder = find_project_folder()

            DOWNLOADS = os.path.join( project_folder, DOWNLOAD_FOLDER)

            image_path = os.path.join(DOWNLOADS, image_filename)  # Save in a 'static' folder

            # Save the image locally (optional)
            with open(image_path, 'wb') as f:
                f.write(image_content)

            # Return the image URL
            image_url = f'/downloads/{image_filename}'  # Adjust the path based on your server setup
            return {'icon_url': icon_url, 'title': title, 'image_url': image_url}

        return {'icon_url': None, 'title': title}
    except Exception as e:
        return {'error': str(e)}

if __name__ == "__main__":
    # Example usage
    result = get_link_icon_and_title('https://www.reddit.com/r/reactjs/comments/irk6yq/how_to_fetch_image_title_etc_from_urls_and/?rdt=34312')
    print(result)
