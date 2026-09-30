import sys
from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from services.news_fetcher import run_all_fetches

def main():
    print("Fetching all news...")
    items = run_all_fetches()
    print(f"Found {len(items)} total items.")
    if items:
        print("Top 3 items:")
        print(json.dumps(items[:3], indent=2))
        
if __name__ == "__main__":
    main()
