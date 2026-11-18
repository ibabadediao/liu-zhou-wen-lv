"""
聊天历史处理类:基于 SQLite 的对话持久化存储
- sessions 表: 存储会话(一次完整对话), 标题默认取首条用户消息截断生成
- messages 表: 存储会话内的每条消息(role: user / assistant)
"""
import os
import sqlite3
from datetime import datetime

from utils.config_handler import agent_config
from utils.path_tool import get_abs_path
from utils.logger_handler import logger

# 会话默认标题, 首条用户消息写入后会自动替换
DEFAULT_TITLE = "新对话"

# 聊天历史数据库的绝对路径, 配置缺失时使用默认路径兜底
DB_PATH = get_abs_path(agent_config.get("chat_db_path", "data/chat_history.db"))


def _connect() -> sqlite3.Connection:
    """
    创建数据库连接, 每次操作独立连接, 避免 Streamlit 多线程共享连接的问题
    :return: sqlite3 连接对象
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # 查询结果可以用列名访问
    return conn


def _init_db():
    """初始化数据库表结构, 模块导入时调用"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = _connect()
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    title      TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    role       TEXT NOT NULL,
                    content    TEXT NOT NULL,
                    files_json TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
            """)

            # 旧库迁移: 会话增加归属用户列; 存量数据保持 NULL, 即"无主会话"不再对外展示
            columns = [row["name"] for row in conn.execute("PRAGMA table_info(sessions)")]
            if "user_id" not in columns:
                conn.execute("ALTER TABLE sessions ADD COLUMN user_id INTEGER")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)"
            )

            # 旧库迁移: 消息表增加 files_json 列, 用于持久化上传文件的元信息(刷新后恢复图片预览)
            msg_columns = [row["name"] for row in conn.execute("PRAGMA table_info(messages)")]
            if "files_json" not in msg_columns:
                conn.execute("ALTER TABLE messages ADD COLUMN files_json TEXT")
                logger.info("[chat_history]messages 表已迁移: 新增 files_json 列")

            # 旧库迁移: 消息表增加 process 列, 用于持久化思考过程(前端折叠展示, 刷新后仍可见)
            if "process" not in msg_columns:
                conn.execute("ALTER TABLE messages ADD COLUMN process TEXT")
                logger.info("[chat_history]messages 表已迁移: 新增 process 列")
    finally:
        conn.close()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_session(user_id: int | None = None, title: str = DEFAULT_TITLE) -> int:
    """
    创建一个新会话
    :param user_id: 归属用户ID, Web 端必传; None 表示本地调试(Streamlit)的无主会话
    :param title: 会话标题
    :return: 会话ID
    """
    conn = _connect()
    try:
        with conn:
            cursor = conn.execute(
                "INSERT INTO sessions(title, created_at, updated_at, user_id) VALUES (?, ?, ?, ?)",
                (title, _now(), _now(), user_id)
            )
        return cursor.lastrowid
    finally:
        conn.close()


def list_sessions(user_id: int | None = None) -> list[dict]:
    """
    查询指定用户的会话, 按最近更新时间倒序
    :param user_id: 用户ID; None 表示查询无主会话(仅本地调试用)
    :return: 会话列表 [{"id": xxx, "title": xxx, "updated_at": xxx}, ...]
    """
    conn = _connect()
    try:
        if user_id is None:
            rows = conn.execute(
                "SELECT id, title, updated_at FROM sessions WHERE user_id IS NULL ORDER BY updated_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, title, updated_at FROM sessions WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,)
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_session(session_id: int) -> dict | None:
    """
    查询会话元信息(含归属用户), 用于接口层校验越权访问
    :param session_id: 会话ID
    :return: {"id", "title", "user_id", ...} 或 None
    """
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, title, user_id, created_at, updated_at FROM sessions WHERE id = ?",
            (session_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_messages(session_id: int) -> list[dict]:
    """
    查询指定会话的全部消息, 按写入顺序返回
    :param session_id: 会话ID
    :return: 消息列表 [{"role": "user"|"assistant", "content": xxx, "uploadedFiles": [...], ...}, ...]
    """
    import json as _json
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT role, content, files_json, process FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,)
        ).fetchall()
        result = []
        for row in rows:
            msg = {"role": row["role"], "content": row["content"]}
            if row["files_json"]:
                try:
                    msg["uploadedFiles"] = _json.loads(row["files_json"])
                except Exception:
                    pass
            if row["process"]:
                msg["process"] = row["process"]
            result.append(msg)
        return result
    finally:
        conn.close()


def add_message(session_id: int, role: str, content: str, files_json: str | None = None, process: str | None = None):
    """
    向指定会话追加一条消息, 同时刷新会话的更新时间;
    若会话还是默认标题且写入的是用户消息, 则自动用消息内容生成会话标题
    :param session_id: 会话ID
    :param role: 角色, user 或 assistant
    :param content: 消息内容
    :param files_json: 上传文件元信息的 JSON 字符串(仅用户消息可能有)
    :param process: 思考过程文本(仅助手消息可能有, 前端折叠展示)
    """
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "INSERT INTO messages(session_id, role, content, files_json, process, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, role, content, files_json, process, _now())
            )

            # 首条用户消息自动生成会话标题
            if role == "user":
                row = conn.execute(
                    "SELECT title FROM sessions WHERE id = ?", (session_id,)
                ).fetchone()
                if row and row["title"] == DEFAULT_TITLE:
                    conn.execute(
                        "UPDATE sessions SET title = ? WHERE id = ?",
                        (content[:20], session_id)
                    )

            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (_now(), session_id)
            )
    finally:
        conn.close()


def delete_session(session_id: int):
    """
    删除指定会话及其全部消息
    :param session_id: 会话ID
    """
    conn = _connect()
    try:
        with conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        logger.info(f"[chat_history]会话{session_id}已删除")
    finally:
        conn.close()


# 模块导入时初始化数据库
_init_db()

if __name__ == '__main__':
    # 简单自测
    sid = create_session()
    print("新会话ID:", sid)

    add_message(sid, "user", "柳州两日游怎么安排？这是一条很长的消息用来测试标题截断效果")
    add_message(sid, "assistant", "推荐第一天游市区百里柳江, 第二天去三江程阳八寨...")
    print("会话列表:", list_sessions())
    print("会话消息:", get_messages(sid))

    delete_session(sid)
    print("删除后会话列表:", list_sessions())
