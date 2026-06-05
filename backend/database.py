import os
import sqlite3
from datetime import datetime

# 获取当前文件所在文件夹，从而拼出绝对路径
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BACKEND_DIR, "classroom.db")

def get_db_connection():
    """获取 SQLite 连接，并开启外键支持、设为 dict 形式"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """初始化数据库表并预置初始数据"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. 创建表
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
        is_active INTEGER DEFAULT 0
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

    # 初始化默认模型
    default_models = [
        ("DeepSeek (在线)", "openai", "https://api.deepseek.com/v1", os.getenv("DEEPSEEK_API_KEY", ""), 1),
        ("Gemini-Antigravity (在线)", "gemini", "https://generativelanguage.googleapis.com", os.getenv("GEMINI_API_KEY", ""), 0),
        ("qwen3.6-35b (本地)", "openai", "http://localhost:8080/v1", "none", 0),
        ("Gemma-9b (本地)", "openai", "http://localhost:11434/v1", "none", 0),
        ("Claude (在线)", "claude", "https://api.anthropic.com", os.getenv("CLAUDE_API_KEY", ""), 0)
    ]
    for name, protocol, base_url, api_key, is_active in default_models:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO model_config (name, protocol, base_url, api_key, is_active) VALUES (?, ?, ?, ?, ?)",
                (name, protocol, base_url, api_key, is_active)
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
