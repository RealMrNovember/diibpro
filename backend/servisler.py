# -*- coding: utf-8 -*-
"""Yardımcı servisler: uyarı motoru + TCMB kur servisi + evrak arşivi uçları."""
import os
import re
import time
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from . import auth
from . import db as dbm
from .evrak_arsivi import ARSIV_DIR

router = APIRouter(prefix="/api")

EVRAK_UZANTILAR = (".pdf", ".docx", ".doc", ".xlsx", ".xls", ".xlsm", ".png", ".jpg", ".jpeg", ".zip", ".xml", ".csv")
EVRAK_KATEGORILER = ("kapasite-raporu", "resmi-belge", "basvuru", "belge-bilgi",
                     "calisma-dosyasi", "kaynak-veri", "beyanname", "fatura", "diger")


def rows(cur):
    return [dict(r) for r in cur.fetchall()]


# ================================================================ UYARI MOTORU
@router.get("/uyarilar")
def uyarilar(user=Depends(auth.require_user)):
    conn = dbm.get_conn()
    fid = user["firma_id"]
    belge = conn.execute("SELECT * FROM belge WHERE firma_id=? ORDER BY id DESC LIMIT 1", (fid,)).fetchone()
    out = []

    if belge:
        bid = belge["id"]
        # 1) belge süresi
        try:
            kalan = (datetime.strptime(belge["sure_sonu"], "%Y-%m-%d").date() - date.today()).days
            if kalan < 0:
                out.append({"tip": "kritik", "baslik": "Belge süresi doldu",
                            "detay": f"{belge['belge_no']} süresi {belge['sure_sonu']} tarihinde doldu — kapatma başvurusu yapılmalı."})
            elif kalan <= 60:
                out.append({"tip": "uyari", "baslik": f"Belge süresine {kalan} gün kaldı",
                            "detay": f"Süre sonu {belge['sure_sonu']} — ek süre ihtiyacını değerlendirin."})
        except ValueError:
            pass

        # 2) taahhüt açığı (gerçekleşme < %100 olan mamuller, süre az/geçmişken)
        acik = rows(conn.execute(
            """SELECT m.ad, m.satir_kodu, m.taahhut_kg,
                      COALESCE((SELECT SUM(k.miktar_kg) FROM ihracat_kalem k
                                JOIN ihracat i ON i.id=k.ihracat_id
                                WHERE i.belge_id=m.belge_id AND k.mamul_id=m.id),0) g
               FROM mamul m WHERE m.belge_id=? AND m.taahhut_kg > 0""", (bid,)))
        eksik = [a for a in acik if a["g"] < a["taahhut_kg"] * 0.999]
        if eksik:
            toplam_eksik = sum(a["taahhut_kg"] - a["g"] for a in eksik)
            out.append({"tip": "uyari", "baslik": f"{len(eksik)} mamulde taahhüt açığı",
                        "detay": f"Toplam {toplam_eksik:,.0f} kg eksik. En büyük: "
                                 + ", ".join(f"{a['ad'][:28]} ({a['taahhut_kg']-a['g']:,.0f} kg)"
                                             for a in sorted(eksik, key=lambda x: x['g']-x['taahhut_kg'])[:3])})

        # 3) izin aşımı (izin tanımlı hammaddede ithalat > izin)
        for h in conn.execute(
            """SELECT h.ad, h.izin_miktari_kg,
                      COALESCE((SELECT SUM(k.miktar_kg) FROM ithalat_kalem k
                                JOIN ithalat i ON i.id=k.ithalat_id
                                WHERE i.belge_id=? AND k.hammadde_id=h.id),0) ithal
               FROM hammadde h WHERE h.firma_id=? AND h.izin_miktari_kg > 0""", (bid, fid)).fetchall():
            if h["ithal"] > h["izin_miktari_kg"]:
                out.append({"tip": "kritik", "baslik": f"{h['ad']}: ithalat izni aşıldı",
                            "detay": f"İzin {h['izin_miktari_kg']:,.0f} kg, ithal edilen {h['ithal']:,.0f} kg."})

        # 4) eksi stok (DİİB dışı/iç piyasa kullanımı)
        eksi = rows(conn.execute(
            """SELECT h.ad,
                  COALESCE((SELECT SUM(k.miktar_kg) FROM ithalat_kalem k
                            JOIN ithalat i ON i.id=k.ithalat_id WHERE i.belge_id=? AND k.hammadde_id=h.id),0)
                - COALESCE((SELECT SUM(k.miktar_kg * r.katsayi) FROM ihracat_kalem k
                            JOIN ihracat i ON i.id=k.ihracat_id JOIN recete r ON r.mamul_id=k.mamul_id
                            WHERE i.belge_id=? AND r.hammadde_id=h.id),0)
                + COALESCE((SELECT SUM(CASE WHEN d.tip IN ('giris','uretim-giris') THEN d.miktar_kg
                                            WHEN d.tip IN ('cikis','uretim-cikis') THEN -d.miktar_kg
                                            ELSE d.miktar_kg END)
                            FROM depo_hareket d WHERE d.firma_id=? AND d.kalem_tipi='hammadde' AND d.kalem_id=h.id),0) stok
               FROM hammadde h WHERE h.firma_id=? AND h.yerli=0""", (bid, bid, fid, fid)))
        negatif = [e for e in eksi if e["stok"] < -1]
        if negatif:
            out.append({"tip": "bilgi", "baslik": f"{len(negatif)} ithal hammaddede eksi bakiye",
                        "detay": "Eşdeğer eşya (iç piyasa) kullanımı: "
                                 + ", ".join(f"{e['ad']} ({e['stok']:,.0f} kg)" for e in negatif[:4])
                                 + ". Yerli alımları Depo'dan giriş olarak işleyin."})

        # 5) açık ihracat beyannameleri
        acik_bey = conn.execute(
            """SELECT COUNT(*) c FROM ihracat WHERE belge_id=? AND beyanname_no != ''
               AND (kapanis_tarihi='' OR kapanis_tarihi='AÇIK')""", (bid,)).fetchone()["c"]
        if acik_bey:
            out.append({"tip": "bilgi", "baslik": f"{acik_bey} ihracat beyannamesi açık görünüyor",
                        "detay": "Kapanış tarihleri işlenmemiş olabilir — kayıtları kontrol edin."})

    # 6) vadesi geçmiş faturalar
    vade = rows(conn.execute(
        """SELECT f.fatura_no, f.tip, f.vade_tarihi, c.unvan,
                  f.tutar - COALESCE((SELECT SUM(o.tutar) FROM odeme o WHERE o.fatura_id=f.id),0) kalan
           FROM fatura f LEFT JOIN cari c ON c.id=f.cari_id
           WHERE f.firma_id=? AND f.durum != 'odendi' AND f.vade_tarihi != ''
             AND f.vade_tarihi < date('now')""", (fid,)))
    vade = [v for v in vade if v["kalan"] > 0.01]
    if vade:
        out.append({"tip": "uyari", "baslik": f"{len(vade)} faturanın vadesi geçti",
                    "detay": ", ".join(f"{v['unvan'] or v['fatura_no']} ({v['kalan']:,.0f})" for v in vade[:3])})

    conn.close()
    sira = {"kritik": 0, "uyari": 1, "bilgi": 2}
    out.sort(key=lambda x: sira.get(x["tip"], 3))
    return out


# ================================================================ TCMB KUR SERVİSİ
_KUR_CACHE: dict[str, dict] = {}


def _tcmb_url(d: date) -> str:
    if d >= date.today():
        return "https://www.tcmb.gov.tr/kurlar/today.xml"
    return f"https://www.tcmb.gov.tr/kurlar/{d.strftime('%Y%m')}/{d.strftime('%d%m%Y')}.xml"


@router.get("/kur")
def kur(tarih: str = "", user=Depends(auth.require_user)):
    """Verilen tarihe (YYYY-MM-DD) ait TCMB döviz satış kurları. Tatilse önceki iş gününe düşer."""
    try:
        hedef = datetime.strptime(tarih, "%Y-%m-%d").date() if tarih else date.today()
    except ValueError:
        raise HTTPException(400, "tarih formatı: YYYY-MM-DD")

    d = min(hedef, date.today())
    for _ in range(8):  # hafta sonu / tatil için geriye yürü
        key = d.isoformat()
        if key in _KUR_CACHE:
            return _KUR_CACHE[key]
        try:
            req = urllib.request.Request(_tcmb_url(d), headers={"User-Agent": "Mozilla/5.0 DIIBPro"})
            with urllib.request.urlopen(req, timeout=10) as r:
                root = ET.fromstring(r.read())
            out = {"tarih": key, "kaynak_tarih": root.attrib.get("Tarih", key)}
            for cur in root.findall("Currency"):
                kod = cur.attrib.get("Kod")
                if kod in ("USD", "EUR"):
                    satis = cur.findtext("ForexSelling") or cur.findtext("BanknoteSelling") or "0"
                    out[kod] = float(satis.replace(",", "."))
            if "USD" in out:
                _KUR_CACHE[key] = out
                return out
        except Exception:
            pass
        d -= timedelta(days=1)
    raise HTTPException(502, "TCMB kur verisi alınamadı")


# ================================================================ EVRAK ARŞİVİ
@router.get("/evrak")
def evrak_list(user=Depends(auth.require_user), q: str = "", kategori: str = ""):
    conn = dbm.get_conn()
    sql = "SELECT * FROM belge_dosya WHERE firma_id=?"
    params = [user["firma_id"]]
    if q:
        sql += " AND (dosya_adi LIKE ? OR aciklama LIKE ?)"
        params += [f"%{q}%"] * 2
    if kategori:
        sql += " AND kategori=?"
        params.append(kategori)
    items = rows(conn.execute(sql + " ORDER BY kategori, dosya_adi", params))
    conn.close()
    for it in items:
        path = os.path.join(ARSIV_DIR, it["dosya_adi"])
        it["boyut"] = os.path.getsize(path) if os.path.isfile(path) else 0
        it["uzanti"] = os.path.splitext(it["dosya_adi"])[1].lower().lstrip(".")
    return items


@router.post("/evrak")
async def evrak_upload(user=Depends(auth.require_user), dosya: UploadFile = File(...),
                       kategori: str = Form("diger"), aciklama: str = Form("")):
    if kategori not in EVRAK_KATEGORILER:
        kategori = "diger"
    ad = os.path.basename(dosya.filename or "evrak")
    if not ad.lower().endswith(EVRAK_UZANTILAR):
        raise HTTPException(400, f"Desteklenmeyen dosya türü: {ad}")
    data = await dosya.read()
    if len(data) > 60 * 1024 * 1024:
        raise HTTPException(400, "Dosya 60 MB'den büyük olamaz")
    os.makedirs(ARSIV_DIR, exist_ok=True)
    conn = dbm.get_conn()
    # aynı isim varsa benzersizleştir
    hedef_ad = ad
    if conn.execute("SELECT 1 FROM belge_dosya WHERE firma_id=? AND dosya_adi=?",
                    (user["firma_id"], hedef_ad)).fetchone():
        kok, uz = os.path.splitext(ad)
        hedef_ad = f"{kok}-{time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:4]}{uz}"
    with open(os.path.join(ARSIV_DIR, hedef_ad), "wb") as f:
        f.write(data)
    belge = conn.execute("SELECT id FROM belge WHERE firma_id=? ORDER BY id DESC LIMIT 1",
                         (user["firma_id"],)).fetchone()
    cur = conn.execute(
        "INSERT INTO belge_dosya (firma_id, belge_id, dosya_adi, kategori, aciklama) VALUES (?,?,?,?,?)",
        (user["firma_id"], belge["id"] if belge else None, hedef_ad, kategori, aciklama.strip()))
    conn.commit()
    conn.close()
    return {"id": cur.lastrowid, "dosya_adi": hedef_ad}


@router.delete("/evrak/{eid}")
def evrak_delete(eid: int, user=Depends(auth.require_user)):
    conn = dbm.get_conn()
    row = conn.execute("SELECT * FROM belge_dosya WHERE id=? AND firma_id=?",
                       (eid, user["firma_id"])).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404)
    conn.execute("DELETE FROM belge_dosya WHERE id=?", (eid,))
    conn.commit()
    conn.close()
    path = os.path.join(ARSIV_DIR, row["dosya_adi"])
    if os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass
    return {"ok": True}
