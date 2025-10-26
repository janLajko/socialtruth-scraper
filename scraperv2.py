import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import requests
import re
import json
import os

WEBHOOK_URL = "xxx"  # Replace with your actual webhook URL

seen_posts_file = 'seen_posts.json'
if os.path.exists(seen_posts_file):
    with open(seen_posts_file, 'r') as f:
      seen_posts = set(json.load(f))
else:
      seen_posts = set()

    # Configure Chrome options for headless mode
chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--window-size=1920,1080')

driver = webdriver.Chrome(options=chrome_options)
driver.get("https://civictracker.us/executive/member/?uuid=3094abf7-4a95-4b8d-8c8d-af7d1c3747a1")
time.sleep(2)

html_content = driver.find_element(By.ID, 'socialPostsContainer').get_attribute('innerHTML')
driver.quit()

soup = BeautifulSoup(html_content, 'html.parser')
all_posts = []
new_posts = []

for post in soup.find_all('div', class_='social-post'):
    post_data = {}

    view_button = post.find('button', class_='view-button')
    if view_button and view_button.get('onclick'):
        import re
        match = re.search(r"window\.open\('([^']+)'", view_button['onclick'])
        post_data['truth_social_link'] = match.group(1) if match else None
    else:
        continue

    if post_data['truth_social_link'] in seen_posts:
        continue

    content_div = post.find('div', class_='post-content')
    if content_div:
        links = content_div.find_all('a', class_='content-link')
        content_html = str(content_div)
        for link in links:
            if link.get('href'):
                content_html = content_html.replace(f">{link.get_text(strip=True)}<", f">{link['href']}<")
        post_data['content'] = BeautifulSoup(content_html, 'html.parser').get_text(strip=True)
    else:
        post_data['content'] = ""

    post_data['media_url'] = None
    video = post.find('video')
    if video:
        source = video.find('source')
        if source and source.get('src'):
            post_data['media_url'] = source['src']
            post_data['media_type'] = 'video'
    else:
        img = post.select_one('.post-media img')
        if img and img.get('src'):
            post_data['media_url'] = img['src']
            post_data['media_type'] = 'image'

    date_div = post.find('div', class_='post-date-bottom')
    if date_div:
        date_str = date_div.get_text(strip=True)
        date_clean = date_str.replace('•', '').strip()
        try:
            from datetime import datetime
            dt = datetime.strptime(date_clean, "%b %d, %Y %I:%M %p")
            post_data['timestamp'] = int(dt.timestamp())
        except:
            try:
                dt = datetime.strptime(date_clean, "%B %d, %Y %I:%M %p")
                post_data['timestamp'] = int(dt.timestamp())
            except:
                post_data['timestamp'] = int(time.time())
        post_data['date_str'] = date_str

    all_posts.append(post_data)
    new_posts.append(post_data)
    seen_posts.add(post_data['truth_social_link'])

if new_posts:
    posts_file = 'posts_data.json'
    if os.path.exists(posts_file):
        with open(posts_file, 'r') as f:
            existing = json.load(f)
    else:
        existing = []

    existing.extend(new_posts)

    with open(posts_file, 'w', encoding='utf-8') as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    with open('new_posts.json', 'w', encoding='utf-8') as f:
        json.dump(new_posts, f, indent=2, ensure_ascii=False)

    latest_post = new_posts[-1]
    # try:
        # response = requests.post(WEBHOOK_URL, json=latest_post)
        # response.raise_for_status()
    # except Exception as e:
    #     print(f"Failed to send webhook: {e}")

with open(seen_posts_file, 'w') as f:
    json.dump(list(seen_posts), f)
