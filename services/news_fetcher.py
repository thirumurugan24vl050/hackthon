"""
HYDRO MIND — Google News Intelligence Layer
Fetches, parses, and classifies news RSS feeds.
"""
import urllib.parse
import xml.etree.ElementTree as ET
import requests
from datetime import datetime
import hashlib
from typing import List, Dict, Optional
from datetime import datetime, timezone
import yaml
from pathlib import Path

from config.settings import GOOGLE_NEWS_BASE, GOOGLE_NEWS_TIMEOUT
from database.db import execute_query

# Load configs
BASE_DIR = Path(__file__).resolve().parent.parent

with open(BASE_DIR / 'config' / 'news_sources.yaml', 'r') as f:
    NEWS_CONFIG = yaml.safe_load(f)
    
with open(BASE_DIR / 'config' / 'official_sources.yaml', 'r') as f:
    OFFICIAL_CONFIG = yaml.safe_load(f)

def _get_source_classification(domain: str) -> str:
    """Classifies a domain as OFFICIAL or SECONDARY."""
    for official_domain in OFFICIAL_CONFIG.get('official_domains', []):
        if domain == official_domain or domain.endswith(f".{official_domain}"):
            return "OFFICIAL"
    return "SECONDARY"

def fetch_news(query: str) -> List[Dict]:
    """Fetches and parses Google News RSS for a specific query."""
    encoded_query = urllib.parse.quote(query)
    url = f"{GOOGLE_NEWS_BASE}?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
    
    items = []
    try:
        response = requests.get(url, timeout=GOOGLE_NEWS_TIMEOUT)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        for item in root.findall('.//item'):
            title = item.findtext('title', '')
            link = item.findtext('link', '')
            pub_date = item.findtext('pubDate', '')
            source_elem = item.find('source')
            
            publisher = source_elem.text if source_elem is not None else "Unknown"
            source_url = source_elem.get('url', '') if source_elem is not None else ""
            
            # Extract domain from source URL
            domain = ""
            if source_url:
                try:
                    domain = urllib.parse.urlparse(source_url).netloc
                except Exception:
                    domain = source_url

            source_type = _get_source_classification(domain)
            
            item_id = hashlib.sha256(link.encode()).hexdigest()
            
            # Strict relevance filter
            title_lower = title.lower()
            if not any(k in title_lower for k in ["bhavani", "erode", "tamil nadu", "mett", "coimbatore", "tiruppur", "nilgiris"]):
                continue

            items.append({
                'id': item_id,
                'title': title,
                'url': link,
                'publisher': publisher,
                'source_domain': domain,
                'source_type': source_type,
                'published_at_raw': pub_date,
                'query': query
            })
            
        return items
    except Exception as e:
        print(f"Error fetching news for {query}: {e}")
        return []

def run_all_fetches():
    """Iterates through all queries, fetches news, and saves to DB."""
    queries = NEWS_CONFIG.get('search_queries', [])
    all_results = []
    
    now_utc = datetime.now(timezone.utc).isoformat()
    
    for query in queries:
        results = fetch_news(query)
        for item in results:
            execute_query(
                """
                INSERT OR IGNORE INTO news_items 
                (id, title, url, publisher, source_domain, published_at_utc, fetched_at_utc, source_type, status, first_seen_at_utc, last_seen_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item['id'], item['title'], item['url'], item['publisher'], 
                    item['source_domain'], item.get('published_at_raw', now_utc), now_utc, 
                    item['source_type'], 'ACTIVE', now_utc, now_utc
                ),
                commit=True
            )
        all_results.extend(results)
        
    return all_results
