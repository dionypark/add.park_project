"""회원가입/로그인 + 세션 토큰 + '이 유저가 만든 thread_id' 소유권 관리.

- 비밀번호는 bcrypt로 해싱해서 저장한다 (평문 저장 금지).
- 로그인하면 랜덤 토큰(세션)을 발급한다 - thread_id와 같은 발상: 토큰 자체가
  "이 사람이 로그인했다"는 증거이고, 브라우저가 쿠키로 들고 있다가 요청마다 실어보낸다.
- user_threads 테이블이 "이 user_id가 이 thread_id를 만들었다"를 기록해서, 로그인만
  하면 어느 기기/브라우저에서 접속하든 자기 대화 목록을 볼 수 있게 한다 (이전의
  브라우저 세션 기반 방식은 새로고침/기기 변경 시 목록이 날아갔었음).
"""
import secrets
import sqlite3
import time
from pathlib import Path

import bcrypt

DB_PATH = Path(__file__).parent / "users.sqlite"
SESSION_TTL_SECONDS = 30 * 24 * 3600  # 30일


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = _connect()
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at REAL NOT NULL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS user_threads (
                user_id INTEGER NOT NULL,
                thread_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                PRIMARY KEY (user_id, thread_id)
            )"""
        )
        conn.commit()
    finally:
        conn.close()


class UsernameTakenError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


def signup(username: str, password: str) -> str:
    """회원가입 후 바로 로그인시켜 세션 토큰을 반환한다."""
    username = username.strip()
    if not username or not password:
        raise InvalidCredentialsError("아이디/비밀번호를 입력해주세요.")

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = _connect()
    try:
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, password_hash, time.time()),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise UsernameTakenError(f"'{username}'은 이미 사용 중인 아이디입니다.")
        user_id = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()[0]
    finally:
        conn.close()
    return _create_session(user_id)


def login(username: str, password: str) -> str:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, password_hash FROM users WHERE username = ?", (username.strip(),)
        ).fetchone()
    finally:
        conn.close()

    if row is None or not bcrypt.checkpw(password.encode(), row[1].encode()):
        raise InvalidCredentialsError("아이디 또는 비밀번호가 일치하지 않습니다.")
    return _create_session(row[0])


def _create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = time.time()
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, now, now + SESSION_TTL_SECONDS),
        )
        conn.commit()
    finally:
        conn.close()
    return token


def get_user(token: str):
    """{"id": ..., "username": ...} 또는 토큰이 없거나 만료됐으면 None."""
    if not token:
        return None
    conn = _connect()
    try:
        row = conn.execute(
            """SELECT users.id, users.username, sessions.expires_at
               FROM sessions JOIN users ON sessions.user_id = users.id
               WHERE sessions.token = ?""",
            (token,),
        ).fetchone()
    finally:
        conn.close()

    if row is None or row[2] < time.time():
        return None
    return {"id": row[0], "username": row[1]}


def logout(token: str):
    conn = _connect()
    try:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
    finally:
        conn.close()


def record_thread(user_id: int, thread_id: str):
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO user_threads (user_id, thread_id, created_at) VALUES (?, ?, ?)",
            (user_id, thread_id, time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def list_user_thread_ids(user_id: int) -> list[str]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT thread_id FROM user_threads WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows]
