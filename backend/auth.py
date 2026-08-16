# -*- coding: utf-8 -*-
"""Oturum tabanlı kimlik doğrulama (HttpOnly çerez + veritabanı oturumu)."""
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException, Request

from . import db as dbm

SESSION_COOKIE = "diib_session"
SESSION_HOURS = 24 * 7


def create_session(conn, kullanici_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = (datetime.now() + timedelta(hours=SESSION_HOURS)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO oturum (token, kullanici_id, expires_at) VALUES (?,?,?)",
                 (token, kullanici_id, expires))
    conn.execute("DELETE FROM oturum WHERE expires_at < datetime('now','localtime')")
    return token


def login(eposta: str, parola: str):
    """Başarılıysa (token, kullanici_dict) döner, değilse None."""
    conn = dbm.get_conn()
    row = conn.execute("SELECT * FROM kullanici WHERE eposta=? AND aktif=1", (eposta.strip().lower(),)).fetchone()
    if not row or not dbm.verify_password(parola, row["parola_hash"]):
        conn.close()
        return None
    token = create_session(conn, row["id"])
    conn.commit()
    user = dict(row)
    conn.close()
    user.pop("parola_hash", None)
    return token, user


def logout(token: str):
    conn = dbm.get_conn()
    conn.execute("DELETE FROM oturum WHERE token=?", (token,))
    conn.commit()
    conn.close()


def get_user(request: Request):
    """Çerezden kullanıcıyı çözer; yoksa None."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    conn = dbm.get_conn()
    row = conn.execute(
        """SELECT k.*, f.unvan firma_unvan, f.kisa_ad firma_kisa_ad
           FROM oturum o JOIN kullanici k ON k.id=o.kullanici_id JOIN firma f ON f.id=k.firma_id
           WHERE o.token=? AND o.expires_at > datetime('now','localtime') AND k.aktif=1""",
        (token,)).fetchone()
    conn.close()
    if not row:
        return None
    user = dict(row)
    user.pop("parola_hash", None)
    return user


def require_user(request: Request):
    """FastAPI dependency — oturum yoksa 401."""
    user = get_user(request)
    if not user:
        raise HTTPException(401, "Oturum gerekli")
    return user
