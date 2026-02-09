import os
import requests
import re
import csv
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

# --- CONFIG ---
SUBDOMAIN = os.getenv('ZENDESK_SUBDOMAIN')
EMAIL = os.getenv('ZENDESK_EMAIL')
TOKEN = os.getenv('ZENDESK_API_TOKEN')
LOCALE = os.getenv('ZENDESK_LOCALE')
AUTH = (EMAIL, TOKEN)
BASE_URL = f'https://{SUBDOMAIN}.zendesk.com/api/v2/help_center'

def sanitize_name(name):
    clean = re.sub(r'[\\/*?:"<>|]', "", str(name))
    return clean[:50].strip()

def download_asset(url, folder_path, filename):
    if not url or not filename: return None
    
    filepath = os.path.join(folder_path, filename)
    try:
        r = requests.get(url, stream=True)
        if r.status_code == 200:
            with open(filepath, 'wb') as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)
            return filename
    except Exception as e:
        print(f"Error downloading {filename}: {e}")
    return None

def get_full_map():
    print("Mapping Help Center hierarchy...")
    cat_res = requests.get(f"{BASE_URL}/categories.json", auth=AUTH).json()
    cats = {c['id']: c['name'] for c in cat_res.get('categories', [])}
    
    sec_res = requests.get(f"{BASE_URL}/sections.json", auth=AUTH).json()
    sec_to_cat = {}
    sec_names = {}
    for s in sec_res.get('sections', []):
        sec_id = s['id']
        cat_id = s['category_id']
        sec_names[sec_id] = s['name']
        sec_to_cat[sec_id] = cats.get(cat_id, "Uncategorized-Category")
        
    return sec_names, sec_to_cat

def process_kb():
    sec_names, sec_to_cat = get_full_map()
    articles_url = f"{BASE_URL}/{LOCALE}/articles.json"
    csv_data = []

    if not os.path.exists("KB_Backup"):
        os.makedirs("KB_Backup")

    while articles_url:
        res = requests.get(articles_url, auth=AUTH).json()
        for article in res.get('articles', []):
            art_id = article['id']
            sec_id = article.get('section_id')
            
            # 1. Metadata
            original_title = article.get('title', 'No Title')
            original_cat = sec_to_cat.get(sec_id, "Uncategorized")
            original_sec = sec_names.get(sec_id, "Uncategorized-Section")
            
            # 2. Paths
            path_parts = ["KB_Backup", sanitize_name(original_cat), sanitize_name(original_sec), 
                          "Published" if not article.get('draft') else "Unpublished", sanitize_name(original_title)]
            long_base_dir = "\\\\?\\" + os.path.abspath(os.path.join(*path_parts))
            media_path = os.path.join(long_base_dir, "assets")
            os.makedirs(media_path, exist_ok=True)

            # --- 3. Handle Media & Attachment List ---
            attach_res = requests.get(f"{BASE_URL}/articles/{art_id}/attachments.json", auth=AUTH).json()
            article_body = article.get('body') or ""
            attachment_links_html = []

            for attach in attach_res.get('article_attachments', []):
                c_url = attach.get('content_url')
                real_filename = attach.get('file_name')
                file_size_mb = round(attach.get('size', 0) / (1024 * 1024), 1)
                
                if c_url and real_filename:
                    fname = download_asset(c_url, media_path, real_filename)
                    if fname:
                        article_body = article_body.replace(c_url, f"assets/{fname}")
                        # HTML for the "Download Box" at bottom of index.html
                        attachment_links_html.append(f"""
                        <div style="display: flex; align-items: flex-start; margin-bottom: 20px; font-family: sans-serif;">
                            <span style="margin-right: 10px; font-size: 20px;">📎</span>
                            <div>
                                <a href="assets/{fname}" style="color: #f05142; text-decoration: none; font-size: 18px;">{real_filename}</a>
                                <div style="color: #333147; font-size: 14px; margin-top: 5px;">
                                    {file_size_mb} MB · <a href="assets/{fname}" download style="color: #14122b; text-decoration: underline;">Download</a>
                                </div>
                            </div>
                        </div>""")

            # --- 4. Handle Video Links (Extraction) ---
            # Regex to find YouTube, Vimeo, or hosted video URLs
            video_links = re.findall(r'src="([^"]*(?:youtube\.com|vimeo\.com|player\.vimeo)[^"]*)"', article_body)
            if video_links:
                with open(os.path.join(long_base_dir, "video_links.txt"), "w") as f:
                    f.write("\n".join(video_links))

            # --- 5. Final HTML Construction ---
            attachments_section = "".join(attachment_links_html)
            full_html = f"""
            <html>
            <head><meta charset="utf-8"></head>
            <body style="font-family: sans-serif; padding: 40px; color: #333147; line-height: 1.6;">
                <h1>{original_title}</h1>
                <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
                <div class="article-content">{article_body}</div>
                <div style="margin-top: 50px; padding-top: 20px; border-top: 2px solid #f9f9f9;">
                    {attachments_section}
                </div>
            </body>
            </html>"""

            with open(os.path.join(long_base_dir, "index.html"), "w", encoding="utf-8") as f:
                f.write(full_html)

            # 6. Add to CSV
            csv_data.append({
                'ID': art_id, 'Original_Title': original_title, 'Category': original_cat,
                'Section': original_sec, 'Videos': "|".join(video_links), 'Video_Count': len(video_links),
                'Updated_Date': article.get('updated_at')
            })
            print(f"✅ Exported: {original_title}")

        articles_url = res.get('next_page')
if __name__ == "__main__":
    process_kb()