# utils/campaign_manager.py

import sqlite3
import os

DB_DIR = "db"
DB_PATH = os.path.join(DB_DIR, "audit.db")

def setup_database():
    """Ensures the campaigns table exists in the database."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            target TEXT,
            notes TEXT
        )
    """)
    conn.commit()
    conn.close()

def create_campaign(name: str, target: str):
    """Creates a new campaign entry."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO campaigns (name, target, notes) VALUES (?, ?, ?)",
            (name, target, "")
        )
        conn.commit()
        return True, "Campaign created successfully."
    except sqlite3.IntegrityError:
        return False, "A campaign with this name already exists."
    finally:
        conn.close()

def get_campaigns():
    """Retrieves a list of all campaigns (id, name)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM campaigns ORDER BY name ASC")
    campaigns = cursor.fetchall()
    conn.close()
    return campaigns

def get_campaign_notes(campaign_id: int):
    """Retrieves the notes for a specific campaign."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT notes FROM campaigns WHERE id = ?", (campaign_id,))
    notes = cursor.fetchone()
    conn.close()
    return notes[0] if notes else ""

def update_campaign_notes(campaign_id: int, notes: str):
    """Updates the notes for a specific campaign."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE campaigns SET notes = ? WHERE id = ?", (notes, campaign_id))
    conn.commit()
    conn.close()

def delete_campaign(campaign_id: int):
    """Deletes a campaign from the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
    conn.commit()
    conn.close()

# Ensure the table exists when this module is first imported
setup_database()