"""
Initialize the HYDRO MIND database.
"""
import sys
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from database.db import init_db
from config.locations import ALL_STATIONS
from database.db import execute_query

def run():
    print("Initializing HYDRO MIND database...")
    init_db()
    
    # Insert stations
    for st in ALL_STATIONS:
        execute_query(
            "INSERT OR IGNORE INTO stations (id, name, latitude, longitude, type) VALUES (?, ?, ?, ?, ?)",
            (st['id'], st['name'], st['latitude'], st['longitude'], st['type']),
            commit=True
        )
    
    print("Database initialized successfully.")

if __name__ == "__main__":
    run()
