# init_db.py
import sqlite3

def init_db():
    # 连接到数据库（如果不存在，会自动创建 scholar.db 文件）
    conn = sqlite3.connect('scholar.db')
    c = conn.cursor()
    
    # 1. 创建会话表 (Sessions)
    # id: 自增主键
    # session_id: 我们生成的唯一标识符 (UUID)
    # title: 会话标题 (例如 "关于Transformer的讨论")
    # session_type: 类型 (chat=单聊, meeting=组会)
    # created_at: 创建时间
    c.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            title TEXT,
            session_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 2. 创建消息表 (Messages)
    # session_id: 关联到哪个会话
    # role: 发言角色 (user, assistant, prof_ai, prof_bio 等)
    # content: 聊天内容
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(session_id) REFERENCES sessions(session_id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ 数据库 scholar.db 初始化成功！表结构已就绪。")

if __name__ == "__main__":
    init_db()