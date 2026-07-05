# utils/audit.py

import sqlite3
import os
from datetime import datetime

DB_DIR = "db"
DB_PATH = os.path.join(DB_DIR, "audit.db")

def setup_database():
    """Ensures the database and table exist."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT
        )
    """)
    conn.commit()
    conn.close()

def log_action(action: str, details: str):
    """Adds a new entry to the audit log."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO audit_log (timestamp, action, details) VALUES (?, ?, ?)",
        (timestamp, action, details)
    )
    conn.commit()
    conn.close()

def get_latest_logs(limit: int = 50):
    """Retrieves the most recent log entries."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT timestamp, action, details FROM audit_log ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    logs = cursor.fetchall()
    conn.close()
    return logs

# Ensure the database is ready on first import
setup_database()