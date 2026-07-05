import sqlite3
import os
from datetime import datetime

DB_DIR = "db"
DB_PATH = os.path.join(DB_DIR, "audit.db")

def setup_database():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            target TEXT,
            notes TEXT,
            status TEXT DEFAULT 'planning',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS campaign_phases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            phase_name TEXT NOT NULL,
            phase_order INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            ttps TEXT DEFAULT '',
            started_at TEXT,
            completed_at TEXT,
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()

def create_campaign(name, target):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO campaigns (name, target, notes) VALUES (?, ?, ?)", (name, target, ""))
        cid = cursor.lastrowid
        default_phases = [
            ("Reconnaissance", 0),
            ("Weaponization", 1),
            ("Delivery", 2),
            ("Exploitation", 3),
            ("Installation", 4),
            ("C2", 5),
            ("Actions on Objective", 6),
        ]
        for pname, porder in default_phases:
            cursor.execute("INSERT INTO campaign_phases (campaign_id, phase_name, phase_order) VALUES (?, ?, ?)", (cid, pname, porder))
        conn.commit()
        return True, "Campaign created successfully."
    except sqlite3.IntegrityError:
        return False, "A campaign with this name already exists."
    finally:
        conn.close()

def get_campaigns():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM campaigns ORDER BY name ASC")
    campaigns = cursor.fetchall()
    conn.close()
    return campaigns

def get_campaign_details(campaign_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,))
    camp = cursor.fetchone()
    if not camp:
        conn.close()
        return None
    col_names = [desc[0] for desc in cursor.description]
    camp_dict = dict(zip(col_names, camp))

    cursor.execute("SELECT * FROM campaign_phases WHERE campaign_id = ? ORDER BY phase_order", (campaign_id,))
    phases = cursor.fetchall()
    phase_cols = [desc[0] for desc in cursor.description]
    camp_dict["phases"] = [dict(zip(phase_cols, p)) for p in phases]
    conn.close()
    return camp_dict

def get_campaign_notes(campaign_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT notes FROM campaigns WHERE id = ?", (campaign_id,))
    notes = cursor.fetchone()
    conn.close()
    return notes[0] if notes else ""

def update_campaign_notes(campaign_id, notes):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE campaigns SET notes = ? WHERE id = ?", (notes, campaign_id))
    conn.commit()
    conn.close()

def update_campaign_status(campaign_id, status):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE campaigns SET status = ? WHERE id = ?", (status, campaign_id))
    conn.commit()
    conn.close()

def update_phase_status(phase_id, status):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if status == "in_progress":
        cursor.execute("UPDATE campaign_phases SET status = ?, started_at = ? WHERE id = ?", (status, now, phase_id))
    elif status == "completed":
        cursor.execute("UPDATE campaign_phases SET status = ?, completed_at = ? WHERE id = ?", (status, now, phase_id))
    else:
        cursor.execute("UPDATE campaign_phases SET status = ? WHERE id = ?", (status, phase_id))
    conn.commit()
    conn.close()

def update_phase_ttps(phase_id, ttps):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE campaign_phases SET ttps = ? WHERE id = ?", (ttps, phase_id))
    conn.commit()
    conn.close()

def delete_campaign(campaign_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM campaign_phases WHERE campaign_id = ?", (campaign_id,))
    cursor.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
    conn.commit()
    conn.close()

def get_campaign_progress(campaign_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM campaign_phases WHERE campaign_id = ?", (campaign_id,))
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM campaign_phases WHERE campaign_id = ? AND status = 'completed'", (campaign_id,))
    done = cursor.fetchone()[0]
    conn.close()
    return (done / total * 100) if total > 0 else 0

setup_database()
