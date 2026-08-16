# -*- coding: utf-8 -*-
"""Fabrika modülleri: Muhasebe (cari/fatura/ödeme), Depo, Üretim (iş emri), Kalite Kontrol."""
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import auth
from . import db as dbm

router = APIRouter(prefix="/api")


def rows(cur):
    return [dict(r) for r in cur.fetchall()]


# ================================================================ CARİ
@router.get("/cari")
def cari_list(user=Depends(auth.require_user), q: str = "", tip: str = ""):
    conn = dbm.get_conn()
    sql = """SELECT c.*,
        COALESCE((SELECT SUM(f.tutar) FROM fatura f WHERE f.cari_id=c.id AND f.tip='satis'),0) satis_toplam,
        COALESCE((SELECT SUM(f.tutar) FROM fatura f WHERE f.cari_id=c.id AND f.tip='alis'),0) alis_toplam,
        COALESCE((SELECT SUM(o.tutar) FROM odeme o WHERE o.cari_id=c.id AND o.yon='tahsilat'),0) tahsilat,
        COALESCE((SELECT SUM(o.tutar) FROM odeme o WHERE o.cari_id=c.id AND o.yon='odeme'),0) odenen
        FROM cari c WHERE c.firma_id=?"""
    params = [user["firma_id"]]
    if q:
        sql += " AND (c.unvan LIKE ? OR c.ulke LIKE ?)"
        params += [f"%{q}%"] * 2
    if tip:
        sql += " AND c.tip=?"
        params.append(tip)
    items = rows(conn.execute(sql + " ORDER BY c.unvan", params))
    conn.close()
    for c in items:
        c["alacak_bakiye"] = round(c["satis_toplam"] - c["tahsilat"], 2)   # müşteriden alacak
        c["borc_bakiye"] = round(c["alis_toplam"] - c["odenen"], 2)        # tedarikçiye borç
    return items


class CariBody(BaseModel):
    unvan: str
    tip: str = "musteri"
    ulke: str = ""
    vergi_no: str = ""
    eposta: str = ""
    telefon: str = ""
    adres: str = ""
    notlar: str = ""


@router.post("/cari")
def cari_create(body: CariBody, user=Depends(auth.require_user)):
    if not body.unvan.strip():
        raise HTTPException(400, "Ünvan gerekli")
    conn = dbm.get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO cari (firma_id, tip, unvan, ulke, vergi_no, eposta, telefon, adres, notlar) VALUES (?,?,?,?,?,?,?,?,?)",
            (user["firma_id"], body.tip, body.unvan.strip(), body.ulke, body.vergi_no,
             body.eposta, body.telefon, body.adres, body.notlar))
        conn.commit()
        return {"id": cur.lastrowid}
    except Exception:
        raise HTTPException(400, "Bu ünvanla cari zaten var")
    finally:
        conn.close()


@router.put("/cari/{cid}")
def cari_update(cid: int, body: CariBody, user=Depends(auth.require_user)):
    conn = dbm.get_conn()
    conn.execute(
        """UPDATE cari SET tip=?, unvan=?, ulke=?, vergi_no=?, eposta=?, telefon=?, adres=?, notlar=?
           WHERE id=? AND firma_id=?""",
        (body.tip, body.unvan.strip(), body.ulke, body.vergi_no, body.eposta, body.telefon,
         body.adres, body.notlar, cid, user["firma_id"]))
    conn.commit()
    conn.close()
    return {"ok": True}


# ================================================================ FATURA
@router.get("/fatura")
def fatura_list(user=Depends(auth.require_user), tip: str = "", durum: str = "", q: str = "",
                baslangic: str = "", bitis: str = ""):
    conn = dbm.get_conn()
    sql = """SELECT f.*, c.unvan cari_unvan,
        COALESCE((SELECT SUM(o.tutar) FROM odeme o WHERE o.fatura_id=f.id),0) odenen
        FROM fatura f LEFT JOIN cari c ON c.id=f.cari_id WHERE f.firma_id=?"""
    params = [user["firma_id"]]
    if tip:
        sql += " AND f.tip=?"; params.append(tip)
    if durum:
        sql += " AND f.durum=?"; params.append(durum)
    if q:
        sql += " AND (f.fatura_no LIKE ? OR c.unvan LIKE ?)"; params += [f"%{q}%"] * 2
    if baslangic:
        sql += " AND f.tarih >= ?"; params.append(baslangic)
    if bitis:
        sql += " AND f.tarih <= ?"; params.append(bitis)
    items = rows(conn.execute(sql + " ORDER BY f.tarih DESC, f.id DESC", params))
    conn.close()
    for f in items:
        f["kalan"] = round((f["tutar"] or 0) - f["odenen"], 2)
    return items


class FaturaBody(BaseModel):
    tip: str
    cari_id: int | None = None
    fatura_no: str = ""
    tarih: str = ""
    vade_tarihi: str = ""
    doviz: str = "USD"
    tutar: float = 0
    aciklama: str = ""


@router.post("/fatura")
def fatura_create(body: FaturaBody, user=Depends(auth.require_user)):
    if body.tip not in ("alis", "satis"):
        raise HTTPException(400, "tip: alis | satis")
    conn = dbm.get_conn()
    cur = conn.execute(
        """INSERT INTO fatura (firma_id, cari_id, tip, fatura_no, tarih, vade_tarihi, doviz, tutar, aciklama)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (user["firma_id"], body.cari_id, body.tip, body.fatura_no, body.tarih,
         body.vade_tarihi, body.doviz, body.tutar, body.aciklama))
    conn.commit()
    conn.close()
    return {"id": cur.lastrowid}


@router.delete("/fatura/{fid}")
def fatura_delete(fid: int, user=Depends(auth.require_user)):
    conn = dbm.get_conn()
    row = conn.execute("SELECT kaynak FROM fatura WHERE id=? AND firma_id=?", (fid, user["firma_id"])).fetchone()
    if not row:
        raise HTTPException(404)
    if row["kaynak"] != "manuel":
        raise HTTPException(400, "Otomatik oluşan fatura silinemez (kaynağı ithalat/ihracat kaydıdır)")
    conn.execute("DELETE FROM fatura WHERE id=?", (fid,))
    conn.commit()
    conn.close()
    return {"ok": True}


class OdemeBody(BaseModel):
    yon: str                       # tahsilat | odeme
    tutar: float
    cari_id: int | None = None
    fatura_id: int | None = None
    tarih: str = ""
    doviz: str = "USD"
    yontem: str = "havale"
    aciklama: str = ""


@router.post("/odeme")
def odeme_create(body: OdemeBody, user=Depends(auth.require_user)):
    if body.yon not in ("tahsilat", "odeme"):
        raise HTTPException(400, "yon: tahsilat | odeme")
    if body.tutar <= 0:
        raise HTTPException(400, "Tutar 0'dan büyük olmalı")
    conn = dbm.get_conn()
    cari_id = body.cari_id
    if body.fatura_id:
        f = conn.execute("SELECT * FROM fatura WHERE id=? AND firma_id=?", (body.fatura_id, user["firma_id"])).fetchone()
        if not f:
            raise HTTPException(404, "Fatura bulunamadı")
        cari_id = cari_id or f["cari_id"]
    conn.execute(
        """INSERT INTO odeme (firma_id, cari_id, fatura_id, yon, tarih, tutar, doviz, yontem, aciklama)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (user["firma_id"], cari_id, body.fatura_id, body.yon,
         body.tarih or time.strftime("%Y-%m-%d"), body.tutar, body.doviz, body.yontem, body.aciklama))
    # fatura durumu güncelle
    if body.fatura_id:
        odenen = conn.execute("SELECT COALESCE(SUM(tutar),0) s FROM odeme WHERE fatura_id=?",
                              (body.fatura_id,)).fetchone()["s"]
        durum = "odendi" if odenen >= (f["tutar"] or 0) - 0.01 else ("kismi" if odenen > 0 else "acik")
        conn.execute("UPDATE fatura SET durum=? WHERE id=?", (durum, body.fatura_id))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/odeme")
def odeme_list(user=Depends(auth.require_user)):
    conn = dbm.get_conn()
    items = rows(conn.execute(
        """SELECT o.*, c.unvan cari_unvan, f.fatura_no
           FROM odeme o LEFT JOIN cari c ON c.id=o.cari_id LEFT JOIN fatura f ON f.id=o.fatura_id
           WHERE o.firma_id=? ORDER BY o.tarih DESC, o.id DESC LIMIT 200""", (user["firma_id"],)))
    conn.close()
    return items


# ================================================================ DEPO
@router.get("/depo")
def depo_stok(user=Depends(auth.require_user)):
    conn = dbm.get_conn()
    belge = conn.execute("SELECT * FROM belge WHERE firma_id=? ORDER BY id DESC LIMIT 1",
                         (user["firma_id"],)).fetchone()
    bid = belge["id"] if belge else -1

    hammaddeler = rows(conn.execute("SELECT * FROM hammadde WHERE firma_id=? ORDER BY yerli, ad", (user["firma_id"],)))
    ithal = {r["hammadde_id"]: r["kg"] for r in conn.execute(
        """SELECT k.hammadde_id, SUM(k.miktar_kg) kg FROM ithalat_kalem k
           JOIN ithalat i ON i.id=k.ithalat_id WHERE i.belge_id=? GROUP BY k.hammadde_id""", (bid,))}
    sarf = {r["hammadde_id"]: r["kg"] for r in conn.execute(
        """SELECT r.hammadde_id, SUM(k.miktar_kg * r.katsayi) kg
           FROM ihracat_kalem k JOIN ihracat i ON i.id=k.ihracat_id
           JOIN recete r ON r.mamul_id=k.mamul_id WHERE i.belge_id=? GROUP BY r.hammadde_id""", (bid,))}
    hrk_h = {r["kalem_id"]: r["net"] for r in conn.execute(
        """SELECT kalem_id, SUM(CASE WHEN tip IN ('giris','uretim-giris') THEN miktar_kg
                                     WHEN tip IN ('cikis','uretim-cikis') THEN -miktar_kg
                                     ELSE miktar_kg END) net
           FROM depo_hareket WHERE firma_id=? AND kalem_tipi='hammadde' GROUP BY kalem_id""", (user["firma_id"],))}

    ham_stok = []
    for h in hammaddeler:
        i = ithal.get(h["id"], 0) or 0
        s = sarf.get(h["id"], 0) or 0
        m = hrk_h.get(h["id"], 0) or 0
        ham_stok.append({**h, "diib_ithal": round(i, 1), "diib_sarf": round(s, 1),
                         "manuel_net": round(m, 1), "stok": round(i - s + m, 1)})

    mamuller = rows(conn.execute("SELECT * FROM mamul WHERE belge_id=? ORDER BY satir_kodu", (bid,)))
    sevk = {r["mamul_id"]: r["kg"] for r in conn.execute(
        """SELECT k.mamul_id, SUM(k.miktar_kg) kg FROM ihracat_kalem k
           JOIN ihracat i ON i.id=k.ihracat_id WHERE i.belge_id=? GROUP BY k.mamul_id""", (bid,))}
    hrk_m = {r["kalem_id"]: r["net"] for r in conn.execute(
        """SELECT kalem_id, SUM(CASE WHEN tip IN ('giris','uretim-giris') THEN miktar_kg
                                     WHEN tip IN ('cikis','uretim-cikis') THEN -miktar_kg
                                     ELSE miktar_kg END) net
           FROM depo_hareket WHERE firma_id=? AND kalem_tipi='mamul' GROUP BY kalem_id""", (user["firma_id"],))}
    mam_stok = []
    for m in mamuller:
        u = hrk_m.get(m["id"], 0) or 0
        sv = sevk.get(m["id"], 0) or 0
        mam_stok.append({**m, "uretim_net": round(u, 1), "sevk": round(sv, 1), "stok": round(u, 1)})

    hareketler = rows(conn.execute(
        """SELECT d.*, k.ad kullanici_ad,
             CASE d.kalem_tipi WHEN 'hammadde' THEN (SELECT ad FROM hammadde WHERE id=d.kalem_id)
                               ELSE (SELECT ad FROM mamul WHERE id=d.kalem_id) END kalem_ad
           FROM depo_hareket d LEFT JOIN kullanici k ON k.id=d.kullanici_id
           WHERE d.firma_id=? ORDER BY d.id DESC LIMIT 100""", (user["firma_id"],)))
    conn.close()
    return {"hammaddeler": ham_stok, "mamuller": mam_stok, "hareketler": hareketler}


class HareketBody(BaseModel):
    kalem_tipi: str        # hammadde | mamul
    kalem_id: int
    tip: str               # giris | cikis | sayim-duzeltme
    miktar_kg: float
    tarih: str = ""
    aciklama: str = ""


@router.post("/depo/hareket")
def depo_hareket_create(body: HareketBody, user=Depends(auth.require_user)):
    if body.kalem_tipi not in ("hammadde", "mamul") or body.tip not in ("giris", "cikis", "sayim-duzeltme"):
        raise HTTPException(400, "Geçersiz hareket türü")
    if body.miktar_kg == 0:
        raise HTTPException(400, "Miktar 0 olamaz")
    conn = dbm.get_conn()
    conn.execute(
        """INSERT INTO depo_hareket (firma_id, kalem_tipi, kalem_id, tip, miktar_kg, tarih, aciklama, kullanici_id)
           VALUES (?,?,?,?,?,?,?,?)""",
        (user["firma_id"], body.kalem_tipi, body.kalem_id, body.tip, abs(body.miktar_kg)
         if body.tip != "sayim-duzeltme" else body.miktar_kg,
         body.tarih or time.strftime("%Y-%m-%d"), body.aciklama, user["id"]))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/depo/hareket/{hid}")
def depo_hareket_delete(hid: int, user=Depends(auth.require_user)):
    conn = dbm.get_conn()
    row = conn.execute("SELECT is_emri_id FROM depo_hareket WHERE id=? AND firma_id=?", (hid, user["firma_id"])).fetchone()
    if not row:
        raise HTTPException(404)
    if row["is_emri_id"]:
        raise HTTPException(400, "İş emrine bağlı hareket silinemez (iş emrini iptal edin)")
    conn.execute("DELETE FROM depo_hareket WHERE id=?", (hid,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ================================================================ KALİTE
@router.get("/kalite")
def kalite_list(user=Depends(auth.require_user), q: str = "", sonuc: str = ""):
    conn = dbm.get_conn()
    sql = """SELECT t.*, k.ad kullanici_ad FROM kalite_test t
             LEFT JOIN kullanici k ON k.id=t.kullanici_id WHERE t.firma_id=?"""
    params = [user["firma_id"]]
    if q:
        sql += " AND (t.urun LIKE ? OR t.parti_no LIKE ?)"; params += [f"%{q}%"] * 2
    if sonuc:
        sql += " AND t.sonuc=?"; params.append(sonuc)
    items = rows(conn.execute(sql + " ORDER BY t.tarih DESC, t.id DESC LIMIT 300", params))
    conn.close()
    return items


class KaliteBody(BaseModel):
    urun: str
    parti_no: str = ""
    tarih: str = ""
    test_turu: str = "viskozite"
    deger: str = ""
    sonuc: str = "uygun"
    notlar: str = ""


@router.post("/kalite")
def kalite_create(body: KaliteBody, user=Depends(auth.require_user)):
    if not body.urun.strip():
        raise HTTPException(400, "Ürün adı gerekli")
    if body.sonuc not in ("uygun", "sartli", "red"):
        raise HTTPException(400, "sonuc: uygun | sartli | red")
    conn = dbm.get_conn()
    cur = conn.execute(
        """INSERT INTO kalite_test (firma_id, tarih, parti_no, urun, test_turu, deger, sonuc, notlar, kullanici_id)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (user["firma_id"], body.tarih or time.strftime("%Y-%m-%d"), body.parti_no, body.urun.strip(),
         body.test_turu, body.deger, body.sonuc, body.notlar, user["id"]))
    conn.commit()
    conn.close()
    return {"id": cur.lastrowid}


@router.delete("/kalite/{tid}")
def kalite_delete(tid: int, user=Depends(auth.require_user)):
    conn = dbm.get_conn()
    conn.execute("DELETE FROM kalite_test WHERE id=? AND firma_id=?", (tid, user["firma_id"]))
    conn.commit()
    conn.close()
    return {"ok": True}


# ================================================================ ÜRETİM (İŞ EMRİ)
@router.get("/isemri")
def isemri_list(user=Depends(auth.require_user), durum: str = ""):
    conn = dbm.get_conn()
    sql = """SELECT e.*, m.ad mamul_ad, m.satir_kodu FROM is_emri e
             JOIN mamul m ON m.id=e.mamul_id WHERE e.firma_id=?"""
    params = [user["firma_id"]]
    if durum:
        sql += " AND e.durum=?"; params.append(durum)
    items = rows(conn.execute(sql + " ORDER BY e.id DESC LIMIT 200", params))
    # reçeteden hammadde ihtiyacı
    for e in items:
        e["ihtiyac"] = rows(conn.execute(
            """SELECT h.ad, ROUND(r.katsayi * ?, 1) kg FROM recete r
               JOIN hammadde h ON h.id=r.hammadde_id WHERE r.mamul_id=? ORDER BY kg DESC""",
            (e["miktar_kg"], e["mamul_id"])))
    conn.close()
    return items


class IsEmriBody(BaseModel):
    mamul_id: int
    miktar_kg: float
    baslangic: str = ""
    bitis: str = ""
    notlar: str = ""


@router.post("/isemri")
def isemri_create(body: IsEmriBody, user=Depends(auth.require_user)):
    if body.miktar_kg <= 0:
        raise HTTPException(400, "Miktar 0'dan büyük olmalı")
    conn = dbm.get_conn()
    say = conn.execute("SELECT COUNT(*) c FROM is_emri WHERE firma_id=?", (user["firma_id"],)).fetchone()["c"]
    no = f"IE-{time.strftime('%Y')}-{say + 1:04d}"
    cur = conn.execute(
        """INSERT INTO is_emri (firma_id, no, mamul_id, miktar_kg, baslangic, bitis, notlar)
           VALUES (?,?,?,?,?,?,?)""",
        (user["firma_id"], no, body.mamul_id, body.miktar_kg,
         body.baslangic or time.strftime("%Y-%m-%d"), body.bitis, body.notlar))
    conn.commit()
    conn.close()
    return {"id": cur.lastrowid, "no": no}


class IsEmriDurum(BaseModel):
    durum: str


@router.put("/isemri/{eid}")
def isemri_update(eid: int, body: IsEmriDurum, user=Depends(auth.require_user)):
    if body.durum not in ("planlandi", "uretimde", "tamamlandi", "iptal"):
        raise HTTPException(400, "Geçersiz durum")
    conn = dbm.get_conn()
    e = conn.execute("SELECT * FROM is_emri WHERE id=? AND firma_id=?", (eid, user["firma_id"])).fetchone()
    if not e:
        raise HTTPException(404)
    if e["durum"] == "tamamlandi" and body.durum != "tamamlandi":
        # tamamlanmış emri geri alma → bağlı hareketleri sil
        conn.execute("DELETE FROM depo_hareket WHERE is_emri_id=?", (eid,))
    if body.durum == "tamamlandi" and e["durum"] != "tamamlandi":
        tarih = time.strftime("%Y-%m-%d")
        conn.execute(
            """INSERT INTO depo_hareket (firma_id, kalem_tipi, kalem_id, tip, miktar_kg, tarih, aciklama, kullanici_id, is_emri_id)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (user["firma_id"], "mamul", e["mamul_id"], "uretim-giris", e["miktar_kg"], tarih,
             f"{e['no']} üretim girişi", user["id"], eid))
        for r in conn.execute("SELECT * FROM recete WHERE mamul_id=?", (e["mamul_id"],)).fetchall():
            conn.execute(
                """INSERT INTO depo_hareket (firma_id, kalem_tipi, kalem_id, tip, miktar_kg, tarih, aciklama, kullanici_id, is_emri_id)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (user["firma_id"], "hammadde", r["hammadde_id"], "uretim-cikis",
                 round(r["katsayi"] * e["miktar_kg"], 2), tarih,
                 f"{e['no']} reçete sarfı", user["id"], eid))
    conn.execute("UPDATE is_emri SET durum=? WHERE id=?", (body.durum, eid))
    conn.commit()
    conn.close()
    return {"ok": True}


# ================================================================ BİRİM ÖZETLERİ (panel)
def _acik_by_doviz(conn, fid, tip):
    return {r["doviz"]: round(r["s"], 2) for r in conn.execute(
        """SELECT f.doviz, SUM(f.tutar - COALESCE((SELECT SUM(o.tutar) FROM odeme o WHERE o.fatura_id=f.id),0)) s
           FROM fatura f WHERE f.firma_id=? AND f.tip=? AND f.durum != 'odendi'
           GROUP BY f.doviz HAVING s > 0.01""", (fid, tip)).fetchall()}


@router.get("/erp/ozet")
def erp_ozet(user=Depends(auth.require_user)):
    conn = dbm.get_conn()
    fid = user["firma_id"]
    alacak_doviz = _acik_by_doviz(conn, fid, "satis")
    borc_doviz = _acik_by_doviz(conn, fid, "alis")
    acik_alacak = sum(alacak_doviz.values())
    acik_borc = sum(borc_doviz.values())
    aktif_emir = conn.execute(
        "SELECT COUNT(*) c FROM is_emri WHERE firma_id=? AND durum IN ('planlandi','uretimde')", (fid,)).fetchone()["c"]
    son30_red = conn.execute(
        """SELECT COUNT(*) c FROM kalite_test WHERE firma_id=? AND sonuc='red'
           AND tarih >= date('now','-30 day')""", (fid,)).fetchone()["c"]
    son30_test = conn.execute(
        """SELECT COUNT(*) c FROM kalite_test WHERE firma_id=? AND tarih >= date('now','-30 day')""", (fid,)).fetchone()["c"]
    cari_sayisi = conn.execute("SELECT COUNT(*) c FROM cari WHERE firma_id=?", (fid,)).fetchone()["c"]
    conn.close()
    return {
        "acik_alacak": round(acik_alacak, 2),
        "acik_borc": round(acik_borc, 2),
        "alacak_doviz": alacak_doviz,
        "borc_doviz": borc_doviz,
        "aktif_is_emri": aktif_emir,
        "kalite_son30_test": son30_test,
        "kalite_son30_red": son30_red,
        "cari_sayisi": cari_sayisi,
    }
