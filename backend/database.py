import os
import sqlite3
from datetime import datetime

# 获取当前文件所在文件夹，从而拼出绝对路径
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BACKEND_DIR, "classroom.db")

def get_db_connection():
    """获取 SQLite 连接，并开启外键支持、设为 dict 形式"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """初始化数据库表并预置初始数据"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. 创建表
    # 聊天会话
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_sessions (
        id TEXT PRIMARY KEY,
        title TEXT,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 聊天消息
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        role TEXT,
        content TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
    );
    """)

    # 记忆日志
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS memory_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        content TEXT,
        summary TEXT,
        level INTEGER DEFAULT 0
    );
    """)

    # 课程大纲与进度
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS course_progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phase TEXT,
        topic TEXT,
        status TEXT,
        score INTEGER DEFAULT 0
    );
    """)

    # 好感度表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS affection (
        id INTEGER PRIMARY KEY,
        value INTEGER DEFAULT 50,
        last_updated DATETIME
    );
    """)

    # 模型配置表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS model_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        protocol TEXT,
        base_url TEXT,
        api_key TEXT,
        is_active INTEGER DEFAULT 0,
        selected_model_id TEXT
    );
    """)

    # 兼容性升级：如果表已经存在，则尝试动态添加新列
    try:
        cursor.execute("ALTER TABLE model_config ADD COLUMN selected_model_id TEXT")
    except sqlite3.OperationalError:
        pass

    # RAG 知识库后端配置表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rag_config (
        id INTEGER PRIMARY KEY DEFAULT 1,
        backend_type TEXT DEFAULT 'chromadb',
        ragflow_url TEXT DEFAULT 'http://localhost/api/v1',
        ragflow_key TEXT DEFAULT '',
        external_url TEXT DEFAULT '',
        external_key TEXT DEFAULT ''
    );
    """)

    # 2. 预置初始数据
    # 初始化好感度
    cursor.execute("SELECT COUNT(*) FROM affection")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO affection (id, value, last_updated) VALUES (1, 50, ?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),)
        )

    # 初始化 RAG 配置（只插一次，默认用 chromadb）
    cursor.execute("SELECT COUNT(*) FROM rag_config")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO rag_config (id, backend_type, ragflow_url, ragflow_key, external_url, external_key) VALUES (1, 'chromadb', 'http://localhost/api/v1', '', '', '')"
        )

    # 初始化默认模型
    default_models = [
        ("DeepSeek (在线)", "openai", "https://api.deepseek.com/v1", os.getenv("DEEPSEEK_API_KEY", ""), 1, "deepseek-chat"),
        ("Antigravity2API (本地)", "openai", "http://localhost:8045/v1", "sk-text", 0, "gemini-3-pro-high"),
        ("Gemini-Antigravity (在线)", "gemini", "https://generativelanguage.googleapis.com", os.getenv("GEMINI_API_KEY", ""), 0, "gemini-3-pro-high"),
        ("qwen3.6-35b (本地)", "openai", "http://localhost:8080/v1", "none", 0, "qwen3.6-35b"),
        ("Gemma-9b (本地)", "openai", "http://localhost:11434/v1", "none", 0, "gemma-9b"),
        ("Claude (在线)", "claude", "https://api.anthropic.com", os.getenv("CLAUDE_API_KEY", ""), 0, "claude-sonnet-4-5-thinking")
    ]
    for name, protocol, base_url, api_key, is_active, selected_model_id in default_models:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO model_config (name, protocol, base_url, api_key, is_active, selected_model_id) VALUES (?, ?, ?, ?, ?, ?)",
                (name, protocol, base_url, api_key, is_active, selected_model_id)
            )
        except sqlite3.Error:
            pass


    # 初始化课程大纲（如果为空）
    cursor.execute("SELECT COUNT(*) FROM course_progress")
    if cursor.fetchone()[0] == 0:
        default_syllabus = [
            ("第一阶段：炼气入道", "灵气感应与纳气入体", "active", 0),
            ("第一阶段：炼气入道", "经脉拓宽与小周天循环", "pending", 0),
            ("第一阶段：炼气入道", "灵力御物与法术初探", "pending", 0),
            ("第二阶段：筑基稳固", "气态灵力液化与筑基丹服用", "pending", 0),
            ("第二阶段：筑基稳固", "神识诞生与外放练习", "pending", 0),
            ("第三阶段：金丹淬炼", "精气神凝聚与金丹雷劫应对", "pending", 0)
        ]
        cursor.executemany(
            "INSERT INTO course_progress (phase, topic, status, score) VALUES (?, ?, ?, ?)",
            default_syllabus
        )

    conn.commit()
    conn.close()
    print("Database initialized successfully.")

if __name__ == "__main__":
    # 简易测试，如果直接运行该文件，从环境变量加载并在当前目录建库
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(BACKEND_DIR), ".env"))
    init_db()
