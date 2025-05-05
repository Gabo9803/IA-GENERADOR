# history_manager.py
import sqlite3
from datetime import datetime

def init_db():
    conn = sqlite3.connect('history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history
                 (session_id TEXT, role TEXT, content TEXT, timestamp DATETIME)''')
    c.execute('''CREATE TABLE IF NOT EXISTS templates
                 (name TEXT PRIMARY KEY, content TEXT)''')
    conn.commit()
    conn.close()

def save_history(db, session_id: str, role: str, content: str) -> None:
    db.execute('INSERT INTO history VALUES (?, ?, ?, ?)',
               (session_id, role, content, datetime.now()))

def get_history(db, session_id: str) -> list:
    cursor = db.execute('SELECT role, content FROM history WHERE session_id = ? ORDER BY timestamp ASC', (session_id,))
    history = [{'role': role, 'content': content} for role, content in cursor.fetchall()][-20:]
    return history

def clear_history(db, session_id: str) -> None:
    db.execute('DELETE FROM history WHERE session_id = ?', (session_id,))

def save_template(db, name: str, content: str) -> None:
    db.execute('INSERT OR REPLACE INTO templates (name, content) VALUES (?, ?)', (name, content))

def get_templates(db) -> list:
    cursor = db.execute('SELECT name, content FROM templates')
    return [{'name': name, 'content': content} for name, content in cursor.fetchall()]