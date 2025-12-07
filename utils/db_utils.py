# utils/db_utils.py
import sqlite3
import uuid
from typing import List, Dict, Optional

DB_PATH = 'scholar.db'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row # 让查询结果变成字典一样的对象，方便读取
    return conn

# --- 会话 (Session) 管理 ---

def create_session(title: str, session_type: str) -> str:
    """创建一个新会话，返回 session_id"""
    session_id = str(uuid.uuid4())
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO sessions (session_id, title, session_type) VALUES (?, ?, ?)",
        (session_id, title, session_type)
    )
    conn.commit()
    conn.close()
    return session_id

def get_all_sessions() -> List[Dict]:
    """获取所有会话列表（按时间倒序）"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM sessions ORDER BY created_at DESC")
    sessions = [dict(row) for row in c.fetchall()]
    conn.close()
    return sessions

def get_session_info(session_id: str) -> Optional[Dict]:
    """获取单个会话的详细信息"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_session(session_id: str):
    """删除会话"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    c.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()

# --- 消息 (Message) 管理 ---

def add_message(session_id: str, role: str, content: str):
    """保存一条消息"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
        (session_id, role, str(content)) # 确保 content 是字符串
    )
    conn.commit()
    conn.close()

def get_messages(session_id: str) -> List[Dict]:
    """获取某会话的所有消息"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,))
    messages = [dict(row) for row in c.fetchall()]
    conn.close()
    return messages