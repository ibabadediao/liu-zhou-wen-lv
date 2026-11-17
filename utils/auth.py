"""
用户认证模块: 用户表、密码哈希、JWT 签发与校验
- 密码使用 PBKDF2-HMAC-SHA256 加盐哈希存储, 不落明文
- 登录凭证以 httpOnly Cookie 下发, 前端 JS 无法读取, 降低 XSS 窃取风险
- 首次启动自动创建管理员账号(可用环境变量 ADMIN_USERNAME / ADMIN_PASSWORD 覆盖)
"""
import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Cookie, HTTPException, Response

from utils.config_handler import agent_config
from utils.path_tool import get_abs_path

# 与聊天历史共用同一个 SQLite 文件, 不同表互不干扰
DB_PATH = get_abs_path(agent_config.get("chat_db_path", "data/chat_history.db"))

COOKIE_NAME = "lz_token"
TOKEN_TTL = timedelta(days=7)
PBKDF2_ROUNDS = 260_000
JWT_ALGORITHM = "HS256"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    """初始化用户表, 模块导入时调用"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = _connect()
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    username      TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at    TEXT NOT NULL
                )
            """)
    finally:
        conn.close()


def _hash_password(password: str) -> str:
    """生成加盐密码哈希, 格式: pbkdf2_sha256$轮数$盐$摘要"""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ROUNDS
    ).hex()
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${salt}${digest}"


def _verify_password(password: str, stored: str) -> bool:
    """校验明文密码与存储的哈希是否匹配, 使用恒定时间比较防时序攻击"""
    try:
        _, rounds, salt, digest = stored.split("$")
        calc = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), int(rounds)
        ).hex()
        return hmac.compare_digest(calc, digest)
    except (ValueError, TypeError):
        return False


def _load_secret() -> str:
    """
    JWT 签名密钥: 优先环境变量, 其次配置文件, 最后自动生成并持久化到 data/.auth_secret
    """
    key = os.environ.get("AUTH_SECRET_KEY") or agent_config.get("auth_secret_key")
    if key:
        return key

    path = get_abs_path("data/.auth_secret")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            saved = f.read().strip()
            if saved:
                return saved

    key = secrets.token_urlsafe(48)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(key)
    return key


SECRET_KEY = _load_secret()


def create_user(username: str, password: str) -> dict:
    """
    注册新用户
    :param username: 用户名(3-32位)
    :param password: 明文密码(6-64位)
    :return: 用户信息 {"id", "username"}
    :raises ValueError: 用户名/密码不合法或用户名已存在
    """
    username = (username or "").strip()
    if not 3 <= len(username) <= 32:
        raise ValueError("用户名长度需为 3-32 位")
    if not 6 <= len(password or "") <= 64:
        raise ValueError("密码长度需为 6-64 位")

    conn = _connect()
    try:
        with conn:
            cursor = conn.execute(
                "INSERT INTO users(username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, _hash_password(password), datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
        return {"id": cursor.lastrowid, "username": username}
    except sqlite3.IntegrityError:
        raise ValueError("用户名已被注册")
    finally:
        conn.close()


def authenticate(username: str, password: str) -> dict | None:
    """
    校验用户名密码
    :return: 校验通过返回 {"id", "username"}, 否则返回 None
    """
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            ((username or "").strip(),),
        ).fetchone()
    finally:
        conn.close()

    if row and _verify_password(password or "", row["password_hash"]):
        return {"id": row["id"], "username": row["username"]}
    return None


def get_user_by_id(user_id: int) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, username FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def issue_token(user: dict) -> str:
    """签发 JWT, sub 存用户ID, 过期时间 TOKEN_TTL"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user["id"]),
        "username": user["username"],
        "iat": now,
        "exp": now + TOKEN_TTL,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def set_auth_cookie(response: Response, token: str):
    """
    下发 httpOnly Cookie:
    - httponly: 前端 JS 读不到, 防 XSS 窃取
    - samesite=lax: 阻止跨站 POST, 缓解 CSRF
    - secure: 仅在 HTTPS 部署时开启(环境变量 COOKIE_SECURE=1)
    """
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=int(TOKEN_TTL.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=os.environ.get("COOKIE_SECURE") == "1",
        path="/",
    )


def clear_auth_cookie(response: Response):
    response.delete_cookie(key=COOKIE_NAME, path="/")


def get_current_user(lz_token: str | None = Cookie(default=None)) -> dict:
    """
    FastAPI 依赖: 从 httpOnly Cookie 解析当前用户, 未登录/过期统一抛 401
    """
    if not lz_token:
        raise HTTPException(status_code=401, detail="未登录")

    try:
        payload = jwt.decode(lz_token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="登录已过期, 请重新登录")
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="登录状态无效, 请重新登录")

    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


def ensure_default_admin():
    """首次启动创建管理员账号, 已存在则跳过"""
    username = os.environ.get("ADMIN_USERNAME", "admin")
    password = os.environ.get("ADMIN_PASSWORD") or agent_config.get("admin_password") or "admin123"
    try:
        create_user(username, password)
    except ValueError:
        pass   # 已存在, 无需处理


_init_db()
ensure_default_admin()
