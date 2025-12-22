import os
import re
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import unquote, urlparse

# Configuration
EXT_DIR = "/home/iamqq/mysite/temp/ext/Takeout/Blogger"
BLOGS = [
    {"name": "iamqq", "path": "Blogs/IamQQ/feed.atom", "img_sub": "iamqq"}
]
OUTPUT_POSTS_DIR = "content/posts"
STATIC_IMG_DIR = "static/images/blogspot"

NS = {'atom': 'http://www.w3.org/2005/Atom', 'blogger': 'http://schemas.google.com/blogger/2018'}

# Translation Map (Original Title -> English Slug)
TRANSLATION_MAP = {
    "Передача температуры хост системы Proxmox  в Home Assistant": "proxmox_temperature_home_assistant",
    "ПСИХОЛОГИЧЕСКАЯ ПОМОЩЬ": "psychological_help",
    "CNTML": "cntml",
    "Ревербератор": "reverberator",
    "Защита персональных данных": "personal_data_protection",
    "Плеер в подарок": "player_gift",
    "Продажа фотоаппарата Никон": "selling_nikon_camera",
    "Продажа на авито": "selling_on_avito",
    "Осень": "autumn",
    "OneTwo Trip": "onetwo_trip",
    "Не доверяйте программистам": "dont_trust_programmers",
    "Я сделал это ": "i_did_it",
    "Диагностирование болезни по месту боли живота": "diagnosing_abdominal_pain",
    "Сплав по Чусовой": "chusovaya_river_rafting",
    "Карта мира": "world_map",
    "Китайский SGSIII": "chinese_sgs3",
    "Twitter / iamqq": "twitter_iamqq",
    "Автомобильное": "automotive",
    "Fitbit Ultra": "fitbit_ultra",
    "Прилетели в Москву": "arrived_in_moscow",
    "Поехали": "lets_go",
    "Телевизор": "televizor"
}

# Tag Translation Map (Original Tag -> English Slug)
TAG_TRANSLATION_MAP = {
    "телевизор": "tv",
    "Домашние дела": "household_chores",
    "Автомобиль": "car",
    "путешествия": "travel",
    "здоровье": "health",
    "работа": "work",
    "видео": "video",
    "гаджеты": "gadgets",
    "клиника": "clinic",
    "живность": "animals",
    "дорога домой": "road_home",
    "карта мира": "world_map",
    "пестня": "song",
    "бугагашеньки": "fun",
    "нигерийские письма": "nigerian_scam",
    "программирование": "programming"
}

def clean_filename(title):
    # Basic transliteration or slugification
    s = title.lower()
    # Simple translit for common characters if not in map
    translit = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'zh',
        'з': 'z', 'и': 'i', 'й': 'j', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
        'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts',
        'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }
    for char, repl in translit.items():
        s = s.replace(char, repl)
    s = re.sub(r'[^\w\s-]', '', s)
    return re.sub(r'[-\s]+', '_', s).strip('_')

def html_to_markdown(html_content, blog_img_dir):
    if not html_content:
        return ""
    
    # 1. Image handling: find <img> and <a><img>
    # Blogger images are usually <a href="original"><img src="thumb"></a>
    # We want to replace these with local path if file exists
    
    # Find all <img> tags
    img_pattern = re.compile(r'<img.*?>', re.IGNORECASE)
    
    def replace_img(match):
        img_tag = match.group(0)
        src_match = re.search(r'src=["\'](.*?)["\']', img_tag, re.IGNORECASE)
        if not src_match:
            return img_tag
        
        src = src_match.group(1)
        # Extract filename from URL (e.g. image.jpg)
        filename = unquote(os.path.basename(urlparse(src).path))
        
        # Search for this filename in Albums
        found_path = None
        albums_root = os.path.join(EXT_DIR, "Albums")
        for root, dirs, files in os.walk(albums_root):
            if filename in files:
                found_path = os.path.join(root, filename)
                break
        
        if found_path:
            # Transliterate image filename while preserving extension
            base_name, ext = os.path.splitext(filename)
            safe_filename = clean_filename(base_name) + ext.lower()
            
            # Copy to static
            dest_rel_path = f"images/blogspot/{blog_img_dir}/{safe_filename}"
            dest_abs_path = os.path.join("static", dest_rel_path)
            os.makedirs(os.path.dirname(dest_abs_path), exist_ok=True)
            shutil.copy2(found_path, dest_abs_path)
            return f'![{safe_filename}](/{dest_rel_path})'
        
        return img_tag # Keep original if not found

    # Simplify links to images (remove the <a> around the <img> if it was just for enlarging)
    html_content = re.sub(r'<a[^>]*href=["\'][^"\']*\.(jpg|png|gif|jpeg|JPG|PNG)["\'][^>]*>(.*?)</a>', r'\2', html_content, flags=re.IGNORECASE | re.DOTALL)
    
    text = img_pattern.sub(replace_img, html_content)
    
    # Basic Markdown conversion
    text = re.sub(r'<(div|p).*?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</(div|p)>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    
    # Links
    text = re.sub(r'<a.*?href=["\'](.*?)["\'].*?>(.*?)</a>', r'[\2](\1)', text, flags=re.IGNORECASE)
    
    # Formatting
    text = re.sub(r'<(b|strong).*?>(.*?)</\1>', r'**\2**', text, flags=re.IGNORECASE)
    text = re.sub(r'<(i|em).*?>(.*?)</\1>', r'*\2*', text, flags=re.IGNORECASE)
    
    # Remove remaining tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Entities
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    
    return text.strip()

def get_summary(markdown_body):
    # Remove images
    text = re.sub(r'!\[.*?\]\(.*?\)', '', markdown_body)
    # Remove URLs from links but keep text
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    # Remove markdown bold/italic
    text = text.replace('**', '').replace('*', '')
    
    # Clean up whitespace
    text = re.sub(r'\n+', ' ', text).strip()
    
    # Try to take first ~200 chars, but end at a sentence boundary if possible
    if len(text) <= 200:
        return text
        
    summary = text[:200]
    # Try to find last sentence end in the first 200 chars
    last_dot = max(summary.rfind('.'), summary.rfind('!'), summary.rfind('?'))
    if last_dot > 100:
        return text[:last_dot+1]
        
    return summary.rsplit(' ', 1)[0] + "..."

def process_blog(blog_conf):
    feed_path = os.path.join(EXT_DIR, blog_conf["path"])
    print(f"Processing {blog_conf['name']} from {feed_path}")
    
    if not os.path.exists(feed_path):
        print(f"  Error: Feed file {feed_path} not found.")
        return

    tree = ET.parse(feed_path)
    root = tree.getroot()
    
    entries = root.findall('atom:entry', NS)
    print(f"  Found {len(entries)} entries.")
    
    os.makedirs(OUTPUT_POSTS_DIR, exist_ok=True)
    
    counter = {}

    for entry in entries:
        # Check if it's a POST (some entries are TEMPLATE or SETTINGS)
        entry_type = entry.find('blogger:type', NS)
        if entry_type is not None and entry_type.text != 'POST':
            continue
            
        status = entry.find('blogger:status', NS)
        if status is not None and status.text != 'LIVE':
             continue

        title_elem = entry.find('atom:title', NS)
        title = title_elem.text if title_elem is not None and title_elem.text else "Untitled"
        title = title.strip()
        
        # Date
        pub_elem = entry.find('atom:published', NS)
        if pub_elem is None:
            pub_elem = entry.find('atom:updated', NS)
        
        if pub_elem is not None:
             # Example: 2010-10-19T15:12:00Z
             try:
                 dt = datetime.strptime(pub_elem.text.split('.')[0].replace('Z', ''), '%Y-%m-%dT%H:%M:%S')
             except:
                 dt = datetime.now()
        else:
            dt = datetime.now()
            
        date_iso = dt.isoformat() + "Z"
        date_ymd = dt.strftime('%Y%m%d')
        
        # Content
        content_elem = entry.find('atom:content', NS)
        html_body = content_elem.text if content_elem is not None else ""
        
        # Tags processing
        processed_tags = []
        for cat in entry.findall('atom:category', NS):
            term = cat.get('term')
            if term and not term.startswith('tag:blogger.com'):
                tag_title = term
                tag_slug = TAG_TRANSLATION_MAP.get(tag_title) or clean_filename(tag_title)
                
                processed_tags.append(tag_title)
                
                # Create taxonomy metadata to force English URL
                tag_meta_dir = os.path.join("content/tags", tag_title.lower())
                os.makedirs(tag_meta_dir, exist_ok=True)
                with open(os.path.join(tag_meta_dir, "_index.md"), "w", encoding="utf-8") as f:
                    f.write(f'---\ntitle: "{tag_title}"\nurl: "/tags/{tag_slug}/"\n---\n')
        
        # Slug/Filename
        if title in TRANSLATION_MAP:
            slug = TRANSLATION_MAP[title]
        else:
            slug = clean_filename(title)
        
        if not slug:
            slug = "untitled"
            
        if slug in counter:
            counter[slug] += 1
            slug = f"{slug}_{counter[slug]}"
        else:
            counter[slug] = 1
            
        filename = f"{date_ymd}_{slug}.md"
        filepath = os.path.join(OUTPUT_POSTS_DIR, filename)
        
        body = html_to_markdown(html_body, blog_conf["img_sub"])
        
        # Extract featured image (the first image in the post)
        featured_image = ""
        img_match = re.search(r'!\[.*?\]\((.*?)\)', body)
        if img_match:
            featured_image = img_match.group(1)
            # Remove the first occurrence of the featured image from the body
            # We escape the image path for use in regex
            escaped_img_path = re.escape(featured_image)
            img_pattern = rf'!\[.*?\]\({escaped_img_path}\)'
            body = re.sub(img_pattern, '', body, count=1).strip()

        description = get_summary(body)
        
        # Escape double quotes for TOML
        escaped_title = title.replace('"', '\\"')
        escaped_description = description.replace('"', '\\"')
        
        image_fm = f'image = "{featured_image}"' if featured_image else ""
        
        post_content = f"""+++
title = "{escaped_title}"
description = "{escaped_description}"
{image_fm}
date = "{date_iso}"
draft = false
tags = {processed_tags}
+++

{body}
"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(post_content)
            
        print(f"  Created {filename}")

def main():
    # Clean output dir first? User didn't ask but usually better
    # for name in os.listdir(OUTPUT_POSTS_DIR):
    #     if name.endswith(".md"):
    #         os.remove(os.path.join(OUTPUT_POSTS_DIR, name))

    for blog in BLOGS:
        process_blog(blog)

if __name__ == "__main__":
    main()
