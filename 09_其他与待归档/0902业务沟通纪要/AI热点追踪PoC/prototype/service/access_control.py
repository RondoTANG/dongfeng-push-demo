from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import base64
from datetime import datetime, timedelta
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from .database import connection, new_id, now_iso
from .settings import ACCESS_KEY_ENCRYPTION_FILE, ADMIN_KEY_FILE, AUTH_SESSION_HOURS


def _now() -> datetime:
    return datetime.now().astimezone()


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _secret_hash(secret: str, salt: bytes) -> str:
    return hashlib.scrypt(secret.encode("utf-8"), salt=salt, n=2**14, r=8, p=1).hex()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _encryption_key() -> bytes:
    """返回访问密钥加密主密钥；部署环境应通过环境变量稳定提供。"""
    configured = os.getenv("AI_HOTSPOT_KEY_ENCRYPTION_SECRET", "").strip()
    if configured:
        direct_key = configured.encode("ascii", errors="ignore")
        try:
            Fernet(direct_key)
            return direct_key
        except (ValueError, TypeError):
            pass
        digest = hashlib.sha256(configured.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)
    if ACCESS_KEY_ENCRYPTION_FILE.is_file():
        return ACCESS_KEY_ENCRYPTION_FILE.read_bytes().strip()
    ACCESS_KEY_ENCRYPTION_FILE.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    ACCESS_KEY_ENCRYPTION_FILE.write_bytes(key + b"\n")
    os.chmod(ACCESS_KEY_ENCRYPTION_FILE, 0o600)
    return key


def _encrypt_secret(secret: str) -> str:
    return Fernet(_encryption_key()).encrypt(secret.encode("utf-8")).decode("ascii")


def _decrypt_secret(token: str) -> str:
    try:
        return Fernet(_encryption_key()).decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("访问密钥密文无法解密，请检查服务器加密主密钥") from exc


def init_access_control() -> None:
    with connection() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS access_keys (
                access_key_id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                secret_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                key_suffix TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'viewer',
                status TEXT NOT NULL DEFAULT 'active',
                expires_at TEXT,
                last_used_at TEXT,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                revoked_at TEXT,
                encrypted_secret TEXT
            )
            """
        )
        columns = {row[1] for row in db.execute("PRAGMA table_info(access_keys)").fetchall()}
        if "encrypted_secret" not in columns:
            db.execute("ALTER TABLE access_keys ADD COLUMN encrypted_secret TEXT")
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS access_sessions (
                session_hash TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                display_name TEXT NOT NULL,
                access_key_id TEXT,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            )
            """
        )
        db.execute("CREATE INDEX IF NOT EXISTS idx_access_keys_status ON access_keys(status)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_access_sessions_expiry ON access_sessions(expires_at)")
        db.execute("DELETE FROM access_sessions WHERE expires_at < ?", (now_iso(),))
    ensure_admin_key()


def ensure_admin_key() -> str:
    configured = os.getenv("AI_HOTSPOT_ADMIN_KEY", "").strip()
    if configured:
        return configured
    if ADMIN_KEY_FILE.is_file():
        return ADMIN_KEY_FILE.read_text(encoding="utf-8").strip()
    ADMIN_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    secret = "ADM-" + secrets.token_urlsafe(24)
    ADMIN_KEY_FILE.write_text(secret + "\n", encoding="utf-8")
    os.chmod(ADMIN_KEY_FILE, 0o600)
    return secret


def authenticate_key(secret: str) -> dict[str, Any] | None:
    secret = secret.strip()
    if not secret:
        return None
    if hmac.compare_digest(secret, ensure_admin_key()):
        return {"role": "admin", "display_name": "系统管理员", "access_key_id": None}
    with connection() as db:
        rows = db.execute(
            "SELECT * FROM access_keys WHERE status='active' AND role='viewer'"
        ).fetchall()
        for row in rows:
            expires_at = _parse_time(row["expires_at"])
            if expires_at and expires_at <= _now():
                db.execute("UPDATE access_keys SET status='expired' WHERE access_key_id=?", (row["access_key_id"],))
                continue
            candidate = _secret_hash(secret, bytes.fromhex(row["salt"]))
            if hmac.compare_digest(candidate, row["secret_hash"]):
                db.execute("UPDATE access_keys SET last_used_at=? WHERE access_key_id=?", (now_iso(), row["access_key_id"]))
                return {"role": "viewer", "display_name": row["label"], "access_key_id": row["access_key_id"]}
    return None


def authenticate_admin_key(secret: str) -> bool:
    secret = secret.strip()
    return bool(secret) and hmac.compare_digest(secret, ensure_admin_key())


def create_session(identity: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    token = secrets.token_urlsafe(32)
    created = _now()
    expires = created + timedelta(hours=AUTH_SESSION_HOURS)
    with connection() as db:
        db.execute(
            """INSERT INTO access_sessions
            (session_hash, role, display_name, access_key_id, created_at, expires_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (_token_hash(token), identity["role"], identity["display_name"], identity.get("access_key_id"),
             created.isoformat(timespec="seconds"), expires.isoformat(timespec="seconds"), created.isoformat(timespec="seconds")),
        )
    return token, {**identity, "expires_at": expires.isoformat(timespec="seconds")}


def get_session(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    with connection() as db:
        row = db.execute("SELECT * FROM access_sessions WHERE session_hash=?", (_token_hash(token),)).fetchone()
        if not row:
            return None
        expires_at = _parse_time(row["expires_at"])
        if not expires_at or expires_at <= _now():
            db.execute("DELETE FROM access_sessions WHERE session_hash=?", (_token_hash(token),))
            return None
        if row["access_key_id"]:
            key = db.execute("SELECT status, expires_at FROM access_keys WHERE access_key_id=?", (row["access_key_id"],)).fetchone()
            key_expiry = _parse_time(key["expires_at"]) if key else None
            if not key or key["status"] != "active" or (key_expiry and key_expiry <= _now()):
                db.execute("DELETE FROM access_sessions WHERE session_hash=?", (_token_hash(token),))
                return None
        db.execute("UPDATE access_sessions SET last_seen_at=? WHERE session_hash=?", (now_iso(), _token_hash(token)))
        return dict(row)


def delete_session(token: str | None) -> None:
    if token:
        with connection() as db:
            db.execute("DELETE FROM access_sessions WHERE session_hash=?", (_token_hash(token),))


def create_viewer_key(label: str, expires_in_days: int | None, created_by: str) -> dict[str, Any]:
    secret = "VIS-" + secrets.token_urlsafe(24)
    salt = secrets.token_bytes(16)
    expires_at = (_now() + timedelta(days=expires_in_days)).isoformat(timespec="seconds") if expires_in_days else None
    access_key_id = new_id("KEY")
    with connection() as db:
        db.execute(
            """INSERT INTO access_keys
            (access_key_id, label, secret_hash, salt, key_suffix, role, status, expires_at, created_at, created_by, encrypted_secret)
            VALUES (?, ?, ?, ?, ?, 'viewer', 'active', ?, ?, ?, ?)""",
            (access_key_id, label, _secret_hash(secret, salt), salt.hex(), secret[-4:], expires_at, now_iso(), created_by, _encrypt_secret(secret)),
        )
    return {"access_key_id": access_key_id, "label": label, "access_key": secret, "role": "viewer",
            "expires_at": expires_at, "message": "可立即复制；之后仍可在管理页再次验证管理员密钥后查看"}


def list_access_keys() -> list[dict[str, Any]]:
    with connection() as db:
        db.execute("UPDATE access_keys SET status='expired' WHERE status='active' AND expires_at IS NOT NULL AND expires_at <= ?", (now_iso(),))
        rows = db.execute(
            """SELECT access_key_id, label, key_suffix, role, status, expires_at, last_used_at,
            created_at, created_by, revoked_at,
            CASE WHEN encrypted_secret IS NOT NULL AND encrypted_secret != '' THEN 1 ELSE 0 END AS can_reveal
            FROM access_keys ORDER BY created_at DESC"""
        ).fetchall()
    return [{**dict(row), "can_reveal": bool(row["can_reveal"])} for row in rows]


def reveal_viewer_key(access_key_id: str, admin_secret: str) -> dict[str, Any]:
    """管理员二次验证后解密访客密钥；旧的仅哈希记录无法恢复。"""
    if not authenticate_admin_key(admin_secret):
        raise PermissionError("管理员密钥验证失败")
    with connection() as db:
        row = db.execute(
            "SELECT access_key_id, label, encrypted_secret, expires_at, status FROM access_keys WHERE access_key_id=?",
            (access_key_id,),
        ).fetchone()
    if not row:
        raise LookupError("访问密钥不存在")
    if not row["encrypted_secret"]:
        raise ValueError("该密钥由旧版本创建，未保存可恢复密文；请停用后重新生成")
    return {
        "access_key_id": row["access_key_id"],
        "label": row["label"],
        "access_key": _decrypt_secret(row["encrypted_secret"]),
        "expires_at": row["expires_at"],
        "status": row["status"],
    }


def revoke_access_key(access_key_id: str) -> bool:
    with connection() as db:
        row = db.execute("SELECT status FROM access_keys WHERE access_key_id=?", (access_key_id,)).fetchone()
        if not row:
            return False
        db.execute("UPDATE access_keys SET status='revoked', revoked_at=? WHERE access_key_id=?", (now_iso(), access_key_id))
        db.execute("DELETE FROM access_sessions WHERE access_key_id=?", (access_key_id,))
    return True
