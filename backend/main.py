# -*- coding: utf-8 -*-
"""DİİBPro — Dahilde İşleme Takip Sistemi (FastAPI backend).

Sayfalar:  /  showcase · /login · /app (oturum gerekli)
Motorlar:  OCR (varsayılan, ücretsiz, yerel Tesseract) · AI (opsiyonel, Claude API)
"""
import json
import os
import time
import uuid

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import auth
from . import db as dbm
from . import erp
from . import ocr as ocr_engine
from . import rapor
from . import servisler

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

_env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(_env_path):
    with open(_env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

app = FastAPI(title="DİİBPro")
dbm.init_db()
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.include_router(erp.router)
app.include_router(rapor.router)
app.include_router(servisler.router)

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf"}


def rows(cur):
    return [dict(r) for r in cur.fetchall()]


def get_belge(conn, user):
    """Kullanıcının firmasının aktif belgesi (şimdilik tek belge)."""
    b = conn.execute("SELECT * FROM belge WHERE firma_id=? ORDER BY id DESC LIMIT 1",
                     (user["firma_id"],)).fetchone()
    if not b:
        raise HTTPException(404, "Firma için tanımlı DİİB yok")
    return dict(b)


def get_meta(conn, user):
    belge = get_belge(conn, user)
    hammaddeler = rows(conn.execute("SELECT * FROM hammadde WHERE firma_id=? ORDER BY yerli, ad", (user["firma_id"],)))
    mamuller = rows(conn.execute("SELECT * FROM mamul WHERE belge_id=? ORDER BY satir_kodu", (belge["id"],)))
    receteler = rows(conn.execute(
        """SELECT r.id, r.mamul_id, r.hammadde_id, r.katsayi, m.satir_kodu, h.ad AS hammadde_ad
           FROM recete r JOIN mamul m ON m.id=r.mamul_id JOIN hammadde h ON h.id=r.hammadde_id
           WHERE m.belge_id=? ORDER BY m.satir_kodu, h.ad""", (belge["id"],)))
    return belge, hammaddeler, mamuller, receteler


# ---------------------------------------------------------------- auth
class LoginBody(BaseModel):
    eposta: str
    parola: str


@app.post("/api/login")
def api_login(body: LoginBody):
    res = auth.login(body.eposta, body.parola)
    if not res:
        raise HTTPException(401, "E-posta veya parola hatalı")
    token, user = res
    resp = JSONResponse({"ok": True, "kullanici": {"ad": user["ad"], "eposta": user["eposta"], "rol": user["rol"]}})
    resp.set_cookie(auth.SESSION_COOKIE, token, httponly=True, samesite="lax",
                    max_age=auth.SESSION_HOURS * 3600)
    return resp


@app.post("/api/logout")
def api_logout(request: Request):
    token = request.cookies.get(auth.SESSION_COOKIE)
    if token:
        auth.logout(token)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(auth.SESSION_COOKIE)
    return resp


@app.get("/api/me")
def api_me(user=Depends(auth.require_user)):
    return {"ad": user["ad"], "eposta": user["eposta"], "rol": user["rol"],
            "firma": user["firma_unvan"], "firma_kisa": user["firma_kisa_ad"]}


# ---------------------------------------------------------------- meta
@app.get("/api/meta")
def api_meta(user=Depends(auth.require_user)):
    conn = dbm.get_conn()
    belge, hammaddeler, mamuller, receteler = get_meta(conn, user)
    conn.close()
    ai_ok = bool(os.environ.get("ANTHROPIC_API_KEY"))
    return {"belge": belge, "hammaddeler": hammaddeler, "mamuller": mamuller,
            "receteler": receteler,
            "motorlar": {"ocr": ocr_engine.available(), "ai": ai_ok}}


class HammaddeUpdate(BaseModel):
    satir_kodu: str | None = None
    gtip: str | None = None
    izin_miktari_kg: float | None = None


@app.put("/api/hammadde/{hid}")
def api_hammadde_update(hid: int, body: HammaddeUpdate, user=Depends(auth.require_user)):
    conn = dbm.get_conn()
    for field in ("satir_kodu", "gtip", "izin_miktari_kg"):
        val = getattr(body, field)
        if val is not None:
            conn.execute(f"UPDATE hammadde SET {field}=? WHERE id=? AND firma_id=?",
                         (val, hid, user["firma_id"]))
    conn.commit()
    conn.close()
    return {"ok": True}


class ReceteUpdate(BaseModel):
    katsayi: float


@app.put("/api/recete/{rid}")
def api_recete_update(rid: int, body: ReceteUpdate, user=Depends(auth.require_user)):
    conn = dbm.get_conn()
    conn.execute(
        """UPDATE recete SET katsayi=? WHERE id=? AND mamul_id IN
           (SELECT m.id FROM mamul m JOIN belge b ON b.id=m.belge_id WHERE b.firma_id=?)""",
        (body.katsayi, rid, user["firma_id"]))
    conn.commit()
    conn.close()
    return {"ok": True}


# ---------------------------------------------------------------- dashboard
@app.get("/api/dashboard")
def api_dashboard(user=Depends(auth.require_user)):
    conn = dbm.get_conn()
    belge, hammaddeler, mamuller, _ = get_meta(conn, user)
    bid = belge["id"]

    ihr = {r["mamul_id"]: r for r in conn.execute(
        """SELECT k.mamul_id, SUM(k.miktar_kg) kg, SUM(k.tutar) tutar
           FROM ihracat_kalem k JOIN ihracat i ON i.id=k.ihracat_id
           WHERE i.belge_id=? GROUP BY k.mamul_id""", (bid,)).fetchall()}
    mamul_rows = []
    for m in mamuller:
        g = ihr.get(m["id"])
        kg = (g["kg"] if g else 0) or 0
        mamul_rows.append({
            **m,
            "gerceklesen_kg": kg,
            "gerceklesen_tutar": (g["tutar"] if g else 0) or 0,
            "kalan_kg": (m["taahhut_kg"] or 0) - kg,
            "oran": round(100 * kg / m["taahhut_kg"], 2) if m["taahhut_kg"] else 0,
        })

    ithal = {r["hammadde_id"]: r["kg"] for r in conn.execute(
        """SELECT k.hammadde_id, SUM(k.miktar_kg) kg FROM ithalat_kalem k
           JOIN ithalat i ON i.id=k.ithalat_id WHERE i.belge_id=? GROUP BY k.hammadde_id""", (bid,)).fetchall()}
    sarf = {r["hammadde_id"]: r["kg"] for r in conn.execute(
        """SELECT r.hammadde_id, SUM(k.miktar_kg * r.katsayi) kg
           FROM ihracat_kalem k JOIN ihracat i ON i.id=k.ihracat_id
           JOIN recete r ON r.mamul_id = k.mamul_id
           WHERE i.belge_id=? GROUP BY r.hammadde_id""", (bid,)).fetchall()}
    ham_rows = []
    for h in hammaddeler:
        i = ithal.get(h["id"], 0) or 0
        s = sarf.get(h["id"], 0) or 0
        ham_rows.append({**h, "ithal_kg": round(i, 2), "sarf_kg": round(s, 2),
                         "stok_kg": round(i - s, 2),
                         "kalan_hak_kg": round((h["izin_miktari_kg"] or 0) - i, 2)})

    toplam = conn.execute(
        """SELECT COALESCE(SUM(k.miktar_kg),0) kg, COALESCE(SUM(k.tutar),0) tutar
           FROM ihracat_kalem k JOIN ihracat i ON i.id=k.ihracat_id WHERE i.belge_id=?""", (bid,)).fetchone()
    ihr_tutar_beyan = conn.execute(
        "SELECT COALESCE(SUM(tutar),0) t FROM ihracat WHERE belge_id=?", (bid,)).fetchone()["t"]
    toplam_ithalat = conn.execute(
        """SELECT COALESCE(SUM(i.tutar),0) t FROM ithalat i WHERE i.belge_id=?""", (bid,)).fetchone()["t"]
    kayit = {
        "ithalat": conn.execute("SELECT COUNT(*) c FROM ithalat WHERE belge_id=?", (bid,)).fetchone()["c"],
        "ihracat": conn.execute("SELECT COUNT(*) c FROM ihracat WHERE belge_id=?", (bid,)).fetchone()["c"],
    }
    # aylık ihracat özeti (kg)
    aylik = rows(conn.execute(
        """SELECT substr(i.tarih,1,7) ay, ROUND(SUM(k.miktar_kg),0) kg
           FROM ihracat_kalem k JOIN ihracat i ON i.id=k.ihracat_id
           WHERE i.belge_id=? AND i.tarih != '' GROUP BY ay ORDER BY ay""", (bid,)))
    conn.close()

    taahhut_toplam_kg = sum(m["taahhut_kg"] or 0 for m in mamuller)
    return {
        "belge": belge,
        "mamuller": mamul_rows,
        "hammaddeler": ham_rows,
        "aylik": aylik,
        "ozet": {
            "taahhut_kg": taahhut_toplam_kg,
            "gerceklesen_kg": round(toplam["kg"], 0),
            "gerceklesen_tutar": round(ihr_tutar_beyan, 2),
            "oran_kg": round(100 * toplam["kg"] / taahhut_toplam_kg, 2) if taahhut_toplam_kg else 0,
            "ithalat_tutar": round(toplam_ithalat, 2),
            **kayit,
        },
    }


# ---------------------------------------------------------------- extraction
@app.post("/api/extract")
async def api_extract(kind: str = Form(...), engine: str = Form("ocr"),
                      files: list[UploadFile] = File(...), user=Depends(auth.require_user)):
    if kind not in ("ithalat", "ihracat"):
        raise HTTPException(400, "kind: ithalat | ihracat")
    if engine not in ("ocr", "ai"):
        raise HTTPException(400, "engine: ocr | ai")

    payload, saved = [], []
    for f in files:
        data = await f.read()
        mt = f.content_type or "image/jpeg"
        if mt not in ALLOWED_TYPES:
            raise HTTPException(400, f"Desteklenmeyen dosya türü: {mt}")
        payload.append((data, mt))
        ext_ = ".pdf" if mt == "application/pdf" else os.path.splitext(f.filename or "")[1] or ".jpg"
        name = f"{kind}_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}{ext_}"
        with open(os.path.join(UPLOAD_DIR, name), "wb") as out:
            out.write(data)
        saved.append(name)

    conn = dbm.get_conn()
    _, hammaddeler, mamuller, _ = get_meta(conn, user)
    conn.close()

    try:
        if engine == "ai":
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise RuntimeError("AI motoru için ANTHROPIC_API_KEY tanımlı değil (.env). OCR motorunu kullanın.")
            from . import extract as ai_engine
            result = ai_engine.extract(kind, payload, hammaddeler, mamuller)
        else:
            result = ocr_engine.extract(kind, payload, hammaddeler, mamuller)
    except RuntimeError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(502, f"Çıkarım hatası: {e}")

    return {"draft": result, "image_paths": saved, "engine": engine}


# ---------------------------------------------------------------- ithalat
class IthalatKalem(BaseModel):
    hammadde_id: int
    aciklama: str = ""
    miktar_kg: float
    birim_fiyat: float = 0
    tutar: float = 0
    gtip: str = ""
    kalem_no: int | None = None


class IthalatCreate(BaseModel):
    beyanname_no: str = ""
    fatura_no: str = ""
    tarih: str = ""
    gumruk: str = ""
    satici: str = ""
    mense: str = ""
    doviz: str = "USD"
    tutar: float = 0
    kur: float = 0
    notlar: str = ""
    kaynak: str = "manuel"
    image_paths: list[str] = []
    kalemler: list[IthalatKalem]


@app.post("/api/ithalat")
def api_ithalat_create(body: IthalatCreate, user=Depends(auth.require_user)):
    if not body.kalemler:
        raise HTTPException(400, "En az bir kalem gerekli")
    conn = dbm.get_conn()
    belge = get_belge(conn, user)
    cur = conn.execute(
        """INSERT INTO ithalat (belge_id, beyanname_no, fatura_no, tarih, gumruk, satici, mense,
               doviz, tutar, kur, notlar, kaynak, image_paths)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (belge["id"], body.beyanname_no, body.fatura_no, body.tarih, body.gumruk, body.satici,
         body.mense, body.doviz, body.tutar, body.kur, body.notlar, body.kaynak,
         json.dumps(body.image_paths)))
    iid = cur.lastrowid
    for n, k in enumerate(body.kalemler, 1):
        conn.execute(
            """INSERT INTO ithalat_kalem (ithalat_id, hammadde_id, aciklama, miktar_kg,
                   birim_fiyat, tutar, gtip, kalem_no) VALUES (?,?,?,?,?,?,?,?)""",
            (iid, k.hammadde_id, k.aciklama, k.miktar_kg, k.birim_fiyat, k.tutar,
             k.gtip, k.kalem_no or n))
    dbm._backfill_muhasebe(conn, user["firma_id"])  # cari + alış faturası otomatik
    conn.commit()
    conn.close()
    return {"id": iid}


def _list_filters(base_sql: str, params: list, q: str, baslangic: str, bitis: str, kaynak: str,
                  text_cols: tuple):
    sql = base_sql
    if q:
        like = " OR ".join(f"{c} LIKE ?" for c in text_cols)
        sql += f" AND ({like})"
        params.extend([f"%{q}%"] * len(text_cols))
    if baslangic:
        sql += " AND tarih >= ?"
        params.append(baslangic)
    if bitis:
        sql += " AND tarih <= ?"
        params.append(bitis)
    if kaynak:
        sql += " AND kaynak = ?"
        params.append(kaynak)
    return sql, params


@app.get("/api/ithalat")
def api_ithalat_list(user=Depends(auth.require_user), q: str = "", baslangic: str = "",
                     bitis: str = "", kaynak: str = ""):
    conn = dbm.get_conn()
    belge = get_belge(conn, user)
    sql, params = _list_filters(
        "SELECT * FROM ithalat WHERE belge_id=?", [belge["id"]], q, baslangic, bitis, kaynak,
        ("beyanname_no", "fatura_no", "satici", "gumruk", "mense"))
    items = rows(conn.execute(sql + " ORDER BY tarih DESC, id DESC", params))
    for it in items:
        it["image_paths"] = json.loads(it["image_paths"] or "[]")
        it["kalemler"] = rows(conn.execute(
            """SELECT k.*, h.ad hammadde_ad FROM ithalat_kalem k
               JOIN hammadde h ON h.id=k.hammadde_id WHERE k.ithalat_id=?""", (it["id"],)))
    conn.close()
    return items


@app.get("/api/ithalat/kalemler")
def api_ithalat_kalemler(user=Depends(auth.require_user), q: str = "", baslangic: str = "",
                         bitis: str = "", kaynak: str = ""):
    """Excel benzeri tablo için kalem-düzeyi düz liste."""
    conn = dbm.get_conn()
    belge = get_belge(conn, user)
    sql = """SELECT k.id kalem_id, i.id ithalat_id, k.aciklama, h.ad hammadde_ad,
                    h.satir_kodu diib_kodu,
                    COALESCE(NULLIF(k.gtip,''), h.gtip) gtip,
                    i.beyanname_no, i.fatura_no, i.tarih,
                    i.satici firma, i.mense ulke, i.gumruk, k.miktar_kg, k.birim_fiyat,
                    k.tutar, i.doviz, i.kur, i.kaynak, i.image_paths,
                    COALESCE(k.kalem_no, ROW_NUMBER() OVER (PARTITION BY i.id ORDER BY k.id)) kalem_no
             FROM ithalat_kalem k
             JOIN ithalat i ON i.id = k.ithalat_id
             JOIN hammadde h ON h.id = k.hammadde_id
             WHERE i.belge_id=?"""
    params = [belge["id"]]
    if q:
        sql += """ AND (i.beyanname_no LIKE ? OR i.fatura_no LIKE ? OR i.satici LIKE ?
                   OR k.aciklama LIKE ? OR h.ad LIKE ?)"""
        params += [f"%{q}%"] * 5
    if baslangic:
        sql += " AND i.tarih >= ?"; params.append(baslangic)
    if bitis:
        sql += " AND i.tarih <= ?"; params.append(bitis)
    if kaynak:
        sql += " AND i.kaynak = ?"; params.append(kaynak)
    items = rows(conn.execute(sql + " ORDER BY i.tarih DESC, i.id DESC, k.id", params))
    conn.close()
    for it in items:
        it["image_paths"] = json.loads(it["image_paths"] or "[]")
    return items


class IthalatKalemUpdate(BaseModel):
    hammadde_id: int | None = None
    aciklama: str | None = None
    miktar_kg: float | None = None
    birim_fiyat: float | None = None
    tutar: float | None = None
    gtip: str | None = None
    kalem_no: int | None = None
    # başlık alanları (aynı beyannamedeki tüm kalemleri etkiler)
    beyanname_no: str | None = None
    tarih: str | None = None
    gumruk: str | None = None
    satici: str | None = None
    mense: str | None = None


@app.put("/api/ithalat/kalem/{kid}")
def api_ithalat_kalem_update(kid: int, body: IthalatKalemUpdate, user=Depends(auth.require_user)):
    conn = dbm.get_conn()
    belge = get_belge(conn, user)
    row = conn.execute(
        """SELECT k.id, k.ithalat_id FROM ithalat_kalem k JOIN ithalat i ON i.id=k.ithalat_id
           WHERE k.id=? AND i.belge_id=?""", (kid, belge["id"])).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Kalem bulunamadı")
    for field in ("hammadde_id", "aciklama", "miktar_kg", "birim_fiyat", "tutar", "gtip", "kalem_no"):
        val = getattr(body, field)
        if val is not None:
            conn.execute(f"UPDATE ithalat_kalem SET {field}=? WHERE id=?", (val, kid))
    for field in ("beyanname_no", "tarih", "gumruk", "satici", "mense"):
        val = getattr(body, field)
        if val is not None:
            conn.execute(f"UPDATE ithalat SET {field}=? WHERE id=?", (val, row["ithalat_id"]))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.delete("/api/ithalat/kalem/{kid}")
def api_ithalat_kalem_delete(kid: int, user=Depends(auth.require_user)):
    conn = dbm.get_conn()
    belge = get_belge(conn, user)
    row = conn.execute(
        """SELECT k.ithalat_id FROM ithalat_kalem k JOIN ithalat i ON i.id=k.ithalat_id
           WHERE k.id=? AND i.belge_id=?""", (kid, belge["id"])).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404)
    conn.execute("DELETE FROM ithalat_kalem WHERE id=?", (kid,))
    kalan = conn.execute("SELECT COUNT(*) c FROM ithalat_kalem WHERE ithalat_id=?",
                         (row["ithalat_id"],)).fetchone()["c"]
    if kalan == 0:
        conn.execute("DELETE FROM ithalat WHERE id=?", (row["ithalat_id"],))
    conn.commit()
    conn.close()
    return {"ok": True, "beyanname_silindi": kalan == 0}


@app.delete("/api/ithalat/{iid}")
def api_ithalat_delete(iid: int, user=Depends(auth.require_user)):
    conn = dbm.get_conn()
    belge = get_belge(conn, user)
    conn.execute("DELETE FROM ithalat WHERE id=? AND belge_id=?", (iid, belge["id"]))
    conn.commit()
    conn.close()
    return {"ok": True}


# ---------------------------------------------------------------- ihracat
class IhracatKalem(BaseModel):
    mamul_id: int
    urun_adi: str = ""
    miktar_kg: float
    birim_fiyat: float = 0
    tutar: float = 0
    gtip: str = ""
    kalem_no: int | None = None


class IhracatCreate(BaseModel):
    fatura_no: str = ""
    beyanname_no: str = ""
    tarih: str = ""
    musteri: str = ""
    ulke: str = ""
    doviz: str = "USD"
    tutar: float = 0
    notlar: str = ""
    kaynak: str = "manuel"
    image_paths: list[str] = []
    kalemler: list[IhracatKalem]


@app.post("/api/ihracat")
def api_ihracat_create(body: IhracatCreate, user=Depends(auth.require_user)):
    if not body.kalemler:
        raise HTTPException(400, "En az bir kalem gerekli")
    conn = dbm.get_conn()
    belge = get_belge(conn, user)
    cur = conn.execute(
        """INSERT INTO ihracat (belge_id, fatura_no, beyanname_no, tarih, musteri, ulke, doviz,
               tutar, notlar, kaynak, image_paths)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (belge["id"], body.fatura_no, body.beyanname_no, body.tarih, body.musteri, body.ulke,
         body.doviz, body.tutar, body.notlar, body.kaynak, json.dumps(body.image_paths)))
    iid = cur.lastrowid
    for n, k in enumerate(body.kalemler, 1):
        conn.execute(
            """INSERT INTO ihracat_kalem (ihracat_id, mamul_id, urun_adi, miktar_kg,
                   birim_fiyat, tutar, gtip, kalem_no) VALUES (?,?,?,?,?,?,?,?)""",
            (iid, k.mamul_id, k.urun_adi, k.miktar_kg, k.birim_fiyat, k.tutar,
             k.gtip, k.kalem_no or n))
    dbm._backfill_muhasebe(conn, user["firma_id"])  # cari + satış faturası otomatik
    conn.commit()
    conn.close()
    return {"id": iid}


@app.get("/api/ihracat")
def api_ihracat_list(user=Depends(auth.require_user), q: str = "", baslangic: str = "",
                     bitis: str = "", kaynak: str = ""):
    conn = dbm.get_conn()
    belge = get_belge(conn, user)
    sql, params = _list_filters(
        "SELECT * FROM ihracat WHERE belge_id=?", [belge["id"]], q, baslangic, bitis, kaynak,
        ("fatura_no", "beyanname_no", "musteri", "ulke"))
    items = rows(conn.execute(sql + " ORDER BY tarih DESC, id DESC", params))
    for it in items:
        it["image_paths"] = json.loads(it["image_paths"] or "[]")
        it["kalemler"] = rows(conn.execute(
            """SELECT k.*, m.satir_kodu, m.ad mamul_ad FROM ihracat_kalem k
               JOIN mamul m ON m.id=k.mamul_id WHERE k.ihracat_id=?""", (it["id"],)))
        it["sarf"] = rows(conn.execute(
            """SELECT h.ad hammadde_ad, ROUND(SUM(k.miktar_kg * r.katsayi), 2) kg
               FROM ihracat_kalem k
               JOIN recete r ON r.mamul_id = k.mamul_id
               JOIN hammadde h ON h.id = r.hammadde_id
               WHERE k.ihracat_id=? GROUP BY h.ad ORDER BY kg DESC""", (it["id"],)))
    conn.close()
    return items


@app.get("/api/ihracat/kalemler")
def api_ihracat_kalemler(user=Depends(auth.require_user), q: str = "", baslangic: str = "",
                         bitis: str = "", kaynak: str = "", kategori: str = ""):
    conn = dbm.get_conn()
    belge = get_belge(conn, user)
    sql = """SELECT k.id kalem_id, i.id ihracat_id, k.urun_adi, m.ad mamul_ad, m.kategori,
                    m.satir_kodu diib_kodu,
                    COALESCE(NULLIF(k.gtip,''), m.gtip) gtip,
                    i.fatura_no, i.beyanname_no, i.tarih,
                    i.musteri firma, i.ulke, i.gumruk, k.miktar_kg, k.birim_fiyat,
                    k.tutar, i.doviz, i.kaynak, i.kapanis_tarihi, i.image_paths,
                    COALESCE(k.kalem_no, ROW_NUMBER() OVER (PARTITION BY i.id ORDER BY k.id)) kalem_no
             FROM ihracat_kalem k
             JOIN ihracat i ON i.id = k.ihracat_id
             JOIN mamul m ON m.id = k.mamul_id
             WHERE i.belge_id=?"""
    params = [belge["id"]]
    if q:
        sql += """ AND (i.fatura_no LIKE ? OR i.beyanname_no LIKE ? OR i.musteri LIKE ?
                   OR k.urun_adi LIKE ? OR m.satir_kodu LIKE ?)"""
        params += [f"%{q}%"] * 5
    if baslangic:
        sql += " AND i.tarih >= ?"; params.append(baslangic)
    if bitis:
        sql += " AND i.tarih <= ?"; params.append(bitis)
    if kaynak:
        sql += " AND i.kaynak = ?"; params.append(kaynak)
    if kategori:
        sql += " AND m.kategori = ?"; params.append(kategori)
    items = rows(conn.execute(sql + " ORDER BY i.tarih DESC, i.id DESC, k.id", params))
    conn.close()
    for it in items:
        it["image_paths"] = json.loads(it["image_paths"] or "[]")
    return items


class IhracatKalemUpdate(BaseModel):
    mamul_id: int | None = None
    urun_adi: str | None = None
    miktar_kg: float | None = None
    birim_fiyat: float | None = None
    tutar: float | None = None
    gtip: str | None = None
    kalem_no: int | None = None
    fatura_no: str | None = None
    beyanname_no: str | None = None
    tarih: str | None = None
    musteri: str | None = None
    ulke: str | None = None


@app.put("/api/ihracat/kalem/{kid}")
def api_ihracat_kalem_update(kid: int, body: IhracatKalemUpdate, user=Depends(auth.require_user)):
    conn = dbm.get_conn()
    belge = get_belge(conn, user)
    row = conn.execute(
        """SELECT k.id, k.ihracat_id FROM ihracat_kalem k JOIN ihracat i ON i.id=k.ihracat_id
           WHERE k.id=? AND i.belge_id=?""", (kid, belge["id"])).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Kalem bulunamadı")
    for field in ("mamul_id", "urun_adi", "miktar_kg", "birim_fiyat", "tutar", "gtip", "kalem_no"):
        val = getattr(body, field)
        if val is not None:
            conn.execute(f"UPDATE ihracat_kalem SET {field}=? WHERE id=?", (val, kid))
    for field in ("fatura_no", "beyanname_no", "tarih", "musteri", "ulke"):
        val = getattr(body, field)
        if val is not None:
            conn.execute(f"UPDATE ihracat SET {field}=? WHERE id=?", (val, row["ihracat_id"]))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.delete("/api/ihracat/kalem/{kid}")
def api_ihracat_kalem_delete(kid: int, user=Depends(auth.require_user)):
    conn = dbm.get_conn()
    belge = get_belge(conn, user)
    row = conn.execute(
        """SELECT k.ihracat_id FROM ihracat_kalem k JOIN ihracat i ON i.id=k.ihracat_id
           WHERE k.id=? AND i.belge_id=?""", (kid, belge["id"])).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404)
    conn.execute("DELETE FROM ihracat_kalem WHERE id=?", (kid,))
    kalan = conn.execute("SELECT COUNT(*) c FROM ihracat_kalem WHERE ihracat_id=?",
                         (row["ihracat_id"],)).fetchone()["c"]
    if kalan == 0:
        conn.execute("DELETE FROM ihracat WHERE id=?", (row["ihracat_id"],))
    conn.commit()
    conn.close()
    return {"ok": True, "fatura_silindi": kalan == 0}


@app.delete("/api/ihracat/{iid}")
def api_ihracat_delete(iid: int, user=Depends(auth.require_user)):
    conn = dbm.get_conn()
    belge = get_belge(conn, user)
    conn.execute("DELETE FROM ihracat WHERE id=? AND belge_id=?", (iid, belge["id"]))
    conn.commit()
    conn.close()
    return {"ok": True}


# ---------------------------------------------------------------- yönetim (birim + kullanıcı)
def require_admin(user):
    if user["rol"] != "admin":
        raise HTTPException(403, "Bu işlem için yönetici yetkisi gerekli")


@app.get("/api/birim")
def api_birim_list(user=Depends(auth.require_user)):
    conn = dbm.get_conn()
    items = rows(conn.execute(
        """SELECT b.*, (SELECT COUNT(*) FROM kullanici k WHERE k.birim_id=b.id) kullanici_sayisi
           FROM birim b WHERE b.firma_id=? ORDER BY b.ad""", (user["firma_id"],)))
    conn.close()
    return items


class BirimCreate(BaseModel):
    ad: str
    aciklama: str = ""


@app.post("/api/birim")
def api_birim_create(body: BirimCreate, user=Depends(auth.require_user)):
    require_admin(user)
    if not body.ad.strip():
        raise HTTPException(400, "Birim adı gerekli")
    conn = dbm.get_conn()
    try:
        cur = conn.execute("INSERT INTO birim (firma_id, ad, aciklama) VALUES (?,?,?)",
                           (user["firma_id"], body.ad.strip(), body.aciklama.strip()))
        conn.commit()
        return {"id": cur.lastrowid}
    except Exception:
        raise HTTPException(400, "Bu isimde bir birim zaten var")
    finally:
        conn.close()


@app.delete("/api/birim/{bid}")
def api_birim_delete(bid: int, user=Depends(auth.require_user)):
    require_admin(user)
    conn = dbm.get_conn()
    conn.execute("UPDATE kullanici SET birim_id=NULL WHERE birim_id=? AND firma_id=?", (bid, user["firma_id"]))
    conn.execute("DELETE FROM birim WHERE id=? AND firma_id=?", (bid, user["firma_id"]))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.get("/api/kullanici")
def api_kullanici_list(user=Depends(auth.require_user)):
    require_admin(user)
    conn = dbm.get_conn()
    items = rows(conn.execute(
        """SELECT k.id, k.eposta, k.ad, k.unvan, k.telefon, k.rol, k.aktif, k.birim_id,
                  b.ad birim_ad, k.created_at
           FROM kullanici k LEFT JOIN birim b ON b.id=k.birim_id
           WHERE k.firma_id=? ORDER BY k.aktif DESC, k.ad""", (user["firma_id"],)))
    conn.close()
    return items


class KullaniciCreate(BaseModel):
    eposta: str
    ad: str
    parola: str
    rol: str = "operator"
    unvan: str = ""
    telefon: str = ""
    birim_id: int | None = None


@app.post("/api/kullanici")
def api_kullanici_create(body: KullaniciCreate, user=Depends(auth.require_user)):
    require_admin(user)
    if body.rol not in ("admin", "operator", "viewer"):
        raise HTTPException(400, "Rol: admin | operator | viewer")
    if len(body.parola) < 6:
        raise HTTPException(400, "Parola en az 6 karakter olmalı")
    if "@" not in body.eposta:
        raise HTTPException(400, "Geçerli bir e-posta girin")
    conn = dbm.get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO kullanici (firma_id, eposta, ad, unvan, telefon, parola_hash, rol, birim_id)
               VALUES (?,?,?,?,?,?,?,?)""",
            (user["firma_id"], body.eposta.strip().lower(), body.ad.strip(), body.unvan.strip(),
             body.telefon.strip(), dbm.hash_password(body.parola), body.rol, body.birim_id))
        conn.commit()
        return {"id": cur.lastrowid}
    except Exception as e:
        if "UNIQUE" in str(e):
            raise HTTPException(400, "Bu e-posta ile kayıtlı kullanıcı var")
        raise
    finally:
        conn.close()


class KullaniciUpdate(BaseModel):
    ad: str | None = None
    unvan: str | None = None
    telefon: str | None = None
    rol: str | None = None
    aktif: int | None = None
    birim_id: int | None = None
    parola: str | None = None


@app.put("/api/kullanici/{kid}")
def api_kullanici_update(kid: int, body: KullaniciUpdate, user=Depends(auth.require_user)):
    require_admin(user)
    conn = dbm.get_conn()
    hedef = conn.execute("SELECT * FROM kullanici WHERE id=? AND firma_id=?", (kid, user["firma_id"])).fetchone()
    if not hedef:
        conn.close()
        raise HTTPException(404, "Kullanıcı bulunamadı")
    if body.aktif == 0 and kid == user["id"]:
        conn.close()
        raise HTTPException(400, "Kendi hesabınızı pasifleştiremezsiniz")
    for field in ("ad", "unvan", "telefon", "rol", "aktif", "birim_id"):
        val = getattr(body, field)
        if val is not None:
            conn.execute(f"UPDATE kullanici SET {field}=? WHERE id=?", (val, kid))
    if body.parola:
        if len(body.parola) < 6:
            conn.close()
            raise HTTPException(400, "Parola en az 6 karakter olmalı")
        conn.execute("UPDATE kullanici SET parola_hash=? WHERE id=?", (dbm.hash_password(body.parola), kid))
    conn.commit()
    conn.close()
    return {"ok": True}


# ---------------------------------------------------------------- profil
class ProfilUpdate(BaseModel):
    ad: str | None = None
    unvan: str | None = None
    telefon: str | None = None
    birim_id: int | None = None
    mevcut_parola: str | None = None
    yeni_parola: str | None = None


@app.get("/api/profil")
def api_profil(user=Depends(auth.require_user)):
    conn = dbm.get_conn()
    row = conn.execute(
        """SELECT k.id, k.eposta, k.ad, k.unvan, k.telefon, k.rol, k.birim_id, b.ad birim_ad, k.created_at
           FROM kullanici k LEFT JOIN birim b ON b.id=k.birim_id WHERE k.id=?""", (user["id"],)).fetchone()
    conn.close()
    return dict(row)


@app.put("/api/profil")
def api_profil_update(body: ProfilUpdate, user=Depends(auth.require_user)):
    conn = dbm.get_conn()
    for field in ("ad", "unvan", "telefon", "birim_id"):
        val = getattr(body, field)
        if val is not None:
            conn.execute(f"UPDATE kullanici SET {field}=? WHERE id=?", (val, user["id"]))
    if body.yeni_parola:
        row = conn.execute("SELECT parola_hash FROM kullanici WHERE id=?", (user["id"],)).fetchone()
        if not body.mevcut_parola or not dbm.verify_password(body.mevcut_parola, row["parola_hash"]):
            conn.close()
            raise HTTPException(400, "Mevcut parola hatalı")
        if len(body.yeni_parola) < 6:
            conn.close()
            raise HTTPException(400, "Yeni parola en az 6 karakter olmalı")
        conn.execute("UPDATE kullanici SET parola_hash=? WHERE id=?",
                     (dbm.hash_password(body.yeni_parola), user["id"]))
    conn.commit()
    conn.close()
    return {"ok": True}


# ---------------------------------------------------------------- sayfalar
@app.get("/")
def landing():
    return FileResponse(os.path.join(FRONTEND_DIR, "landing.html"))


@app.get("/login")
def login_page(request: Request):
    if auth.get_user(request):
        return RedirectResponse("/app")
    return FileResponse(os.path.join(FRONTEND_DIR, "login.html"))


@app.get("/app")
def app_page(request: Request):
    if not auth.get_user(request):
        return RedirectResponse("/login")
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/uploads/{name:path}")
def uploaded_file(name: str, user=Depends(auth.require_user)):
    # yol güvenliği: uploads dışına çıkışı engelle
    path = os.path.normpath(os.path.join(UPLOAD_DIR, name))
    if not path.startswith(os.path.normpath(UPLOAD_DIR)) or not os.path.isfile(path):
        raise HTTPException(404)
    return FileResponse(path)


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
