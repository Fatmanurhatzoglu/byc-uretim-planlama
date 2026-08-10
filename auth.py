"""Kimlik doğrulama ve yetki kontrolü."""

from __future__ import annotations

from functools import wraps

from flask import jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import kullanici_getir, kullanici_kullanici_adi_ile


def sifre_hash(sifre: str) -> str:
    return generate_password_hash(sifre)


def sifre_dogrula(hash_deger: str, sifre: str) -> bool:
    return check_password_hash(hash_deger, sifre)


def oturum_ac(kullanici_adi: str, sifre: str) -> dict | None:
    k = kullanici_kullanici_adi_ile(kullanici_adi)
    if k and sifre_dogrula(k["sifre_hash"], sifre):
        return {"id": k["id"], "kullanici_adi": k["kullanici_adi"], "rol": k["rol"], "ad": k["ad"]}
    return None


def oturum_kullanicisi() -> dict | None:
    uid = session.get("kullanici_id")
    if not uid:
        return None
    k = kullanici_getir(uid)
    if not k:
        session.clear()
        return None
    return {"id": k["id"], "kullanici_adi": k["kullanici_adi"], "rol": k["rol"], "ad": k["ad"]}


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not oturum_kullanicisi():
            if request.path.startswith("/api/"):
                return jsonify({"hata": "Giriş gerekli."}), 401
            return redirect(url_for("login_sayfa"))
        return f(*args, **kwargs)
    return decorated


def role_required(*roller):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            k = oturum_kullanicisi()
            if not k:
                if request.path.startswith("/api/"):
                    return jsonify({"hata": "Giriş gerekli."}), 401
                return redirect(url_for("login_sayfa"))
            if k["rol"] not in roller:
                if request.path.startswith("/api/"):
                    return jsonify({"hata": "Yetkiniz yok."}), 403
                return redirect(url_for("ana_sayfa"))
            return f(*args, **kwargs)
        return decorated
    return decorator
