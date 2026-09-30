import sqlite3
from pathlib import Path
from typing import Optional
from config.settings import DB_PATH

def get_connection() -> sqlite3.Connection:
    """Gets a connection to the SQLite database."""
    # Ensure directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # Access columns by name
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Initializes the database using schema.sql."""
    schema_path = Path(__file__).parent / "schema.sql"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found at {schema_path}")
        
    with get_connection() as conn:
        with open(schema_path, 'r', encoding='utf-8') as f:
            conn.executescript(f.read())
            
def execute_query(query: str, params: tuple = (), commit: bool = False) -> Optional[list]:
    """Helper to execute a query and optionally return results or commit."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        
        if commit:
            conn.commit()
            return cursor.lastrowid
        else:
            return [dict(row) for row in cursor.fetchall()]

def execute_many(query: str, params_list: list[tuple]):
    """Helper to execute a query with multiple parameter sets."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany(query, params_list)
        conn.commit()
