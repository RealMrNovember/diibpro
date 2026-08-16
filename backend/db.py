# -*- coding: utf-8 -*-
"""SQLite veritabanı: çok firmalı (multi-tenant) şema + tohum verisi.

İlk müşteri: MATEK KİMYA SAN. TİC. A.Ş. — geçmiş kayıtlar import_history.py ile
Excel'den yüklenir.
"""
import hashlib
import json
import os
import re
import secrets
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "diib.db")
SEED_PATH = os.path.join(BASE_DIR, "data", "seed_data.json")

SCHEMA = """
CREATE TABLE IF NOT EXISTS firma (
    id INTEGER PRIMARY KEY,
    unvan TEXT NOT NULL,
    kisa_ad TEXT DEFAULT '',
    vergi_no TEXT DEFAULT '',
    adres TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS birim (
    id INTEGER PRIMARY KEY,
    firma_id INTEGER NOT NULL REFERENCES firma(id),
    ad TEXT NOT NULL,
    aciklama TEXT DEFAULT '',
    UNIQUE(firma_id, ad)
);

CREATE TABLE IF NOT EXISTS kullanici (
    id INTEGER PRIMARY KEY,
    firma_id INTEGER NOT NULL REFERENCES firma(id),
    birim_id INTEGER REFERENCES birim(id) ON DELETE SET NULL,
    eposta TEXT NOT NULL UNIQUE,
    ad TEXT DEFAULT '',
    unvan TEXT DEFAULT '',
    telefon TEXT DEFAULT '',
    parola_hash TEXT NOT NULL,
    rol TEXT DEFAULT 'admin',          -- admin | operator | viewer
    aktif INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS oturum (
    token TEXT PRIMARY KEY,
    kullanici_id INTEGER NOT NULL REFERENCES kullanici(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS belge (
    id INTEGER PRIMARY KEY,
    firma_id INTEGER NOT NULL REFERENCES firma(id),
    belge_no TEXT NOT NULL,
    belge_tarihi TEXT,
    sure_sonu TEXT,
    durum TEXT DEFAULT 'acik',         -- acik | kapatildi
    ongorulen_ihracat_usd REAL DEFAULT 0,
    ongorulen_ithalat_usd REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS hammadde (
    id INTEGER PRIMARY KEY,
    firma_id INTEGER NOT NULL REFERENCES firma(id),
    satir_kodu TEXT DEFAULT '',
    ad TEXT NOT NULL,
    gtip TEXT DEFAULT '',
    izin_miktari_kg REAL DEFAULT 0,
    yerli INTEGER DEFAULT 0,
    UNIQUE(firma_id, ad)
);

CREATE TABLE IF NOT EXISTS mamul (
    id INTEGER PRIMARY KEY,
    belge_id INTEGER NOT NULL REFERENCES belge(id),
    satir_kodu TEXT NOT NULL,
    grup TEXT NOT NULL,
    ad TEXT NOT NULL,
    gtip TEXT DEFAULT '',
    taahhut_kg REAL DEFAULT 0,
    birim_fiyat_usd REAL DEFAULT 0,
    UNIQUE(belge_id, satir_kodu)
);

CREATE TABLE IF NOT EXISTS recete (
    id INTEGER PRIMARY KEY,
    mamul_id INTEGER NOT NULL REFERENCES mamul(id) ON DELETE CASCADE,
    hammadde_id INTEGER NOT NULL REFERENCES hammadde(id) ON DELETE CASCADE,
    katsayi REAL NOT NULL,
    UNIQUE(mamul_id, hammadde_id)
);

CREATE TABLE IF NOT EXISTS ithalat (
    id INTEGER PRIMARY KEY,
    belge_id INTEGER NOT NULL REFERENCES belge(id),
    beyanname_no TEXT DEFAULT '',
    fatura_no TEXT DEFAULT '',
    tarih TEXT DEFAULT '',
    gumruk TEXT DEFAULT '',
    satici TEXT DEFAULT '',
    mense TEXT DEFAULT '',
    doviz TEXT DEFAULT 'USD',
    tutar REAL DEFAULT 0,
    kur REAL DEFAULT 0,
    notlar TEXT DEFAULT '',
    kaynak TEXT DEFAULT 'manuel',      -- manuel | ocr | ai | excel-aktarim
    image_paths TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS ithalat_kalem (
    id INTEGER PRIMARY KEY,
    ithalat_id INTEGER NOT NULL REFERENCES ithalat(id) ON DELETE CASCADE,
    hammadde_id INTEGER NOT NULL REFERENCES hammadde(id),
    aciklama TEXT DEFAULT '',
    miktar_kg REAL NOT NULL,
    birim_fiyat REAL DEFAULT 0,
    tutar REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ihracat (
    id INTEGER PRIMARY KEY,
    belge_id INTEGER NOT NULL REFERENCES belge(id),
    fatura_no TEXT DEFAULT '',
    beyanname_no TEXT DEFAULT '',
    tarih TEXT DEFAULT '',
    musteri TEXT DEFAULT '',
    ulke TEXT DEFAULT '',
    gumruk TEXT DEFAULT '',
    doviz TEXT DEFAULT 'USD',
    tutar REAL DEFAULT 0,
    kapanis_tarihi TEXT DEFAULT '',
    notlar TEXT DEFAULT '',
    kaynak TEXT DEFAULT 'manuel',
    image_paths TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS ihracat_kalem (
    id INTEGER PRIMARY KEY,
    ihracat_id INTEGER NOT NULL REFERENCES ihracat(id) ON DELETE CASCADE,
    mamul_id INTEGER NOT NULL REFERENCES mamul(id),
    urun_adi TEXT DEFAULT '',
    miktar_kg REAL NOT NULL,
    birim_fiyat REAL DEFAULT 0,
    tutar REAL DEFAULT 0
);

-- ================= FABRİKA MODÜLLERİ =================
CREATE TABLE IF NOT EXISTS cari (
    id INTEGER PRIMARY KEY,
    firma_id INTEGER NOT NULL REFERENCES firma(id),
    tip TEXT DEFAULT 'musteri',        -- musteri | tedarikci
    unvan TEXT NOT NULL,
    ulke TEXT DEFAULT '',
    vergi_no TEXT DEFAULT '',
    eposta TEXT DEFAULT '',
    telefon TEXT DEFAULT '',
    adres TEXT DEFAULT '',
    notlar TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(firma_id, unvan)
);

CREATE TABLE IF NOT EXISTS fatura (
    id INTEGER PRIMARY KEY,
    firma_id INTEGER NOT NULL REFERENCES firma(id),
    cari_id INTEGER REFERENCES cari(id),
    tip TEXT NOT NULL,                 -- alis | satis
    fatura_no TEXT DEFAULT '',
    tarih TEXT DEFAULT '',
    vade_tarihi TEXT DEFAULT '',
    doviz TEXT DEFAULT 'USD',
    tutar REAL DEFAULT 0,
    durum TEXT DEFAULT 'acik',         -- acik | kismi | odendi
    kaynak TEXT DEFAULT 'manuel',      -- manuel | ithalat | ihracat
    ref_id INTEGER,                    -- ithalat/ihracat kaydı id
    aciklama TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS odeme (
    id INTEGER PRIMARY KEY,
    firma_id INTEGER NOT NULL REFERENCES firma(id),
    cari_id INTEGER REFERENCES cari(id),
    fatura_id INTEGER REFERENCES fatura(id) ON DELETE SET NULL,
    yon TEXT NOT NULL,                 -- tahsilat | odeme
    tarih TEXT DEFAULT '',
    tutar REAL NOT NULL,
    doviz TEXT DEFAULT 'USD',
    yontem TEXT DEFAULT 'havale',      -- havale | nakit | cek | kredi-karti
    aciklama TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS depo_hareket (
    id INTEGER PRIMARY KEY,
    firma_id INTEGER NOT NULL REFERENCES firma(id),
    kalem_tipi TEXT NOT NULL,          -- hammadde | mamul
    kalem_id INTEGER NOT NULL,
    tip TEXT NOT NULL,                 -- giris | cikis | sayim-duzeltme | uretim-giris | uretim-cikis
    miktar_kg REAL NOT NULL,           -- sayım düzeltmede +/- fark
    tarih TEXT DEFAULT '',
    aciklama TEXT DEFAULT '',
    kullanici_id INTEGER REFERENCES kullanici(id),
    is_emri_id INTEGER,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS kalite_test (
    id INTEGER PRIMARY KEY,
    firma_id INTEGER NOT NULL REFERENCES firma(id),
    tarih TEXT DEFAULT '',
    parti_no TEXT DEFAULT '',
    urun TEXT NOT NULL,
    test_turu TEXT DEFAULT '',         -- viskozite | renk | yogunluk | kuruma | yapisma | diger
    deger TEXT DEFAULT '',
    sonuc TEXT DEFAULT 'uygun',        -- uygun | sartli | red
    notlar TEXT DEFAULT '',
    kullanici_id INTEGER REFERENCES kullanici(id),
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS is_emri (
    id INTEGER PRIMARY KEY,
    firma_id INTEGER NOT NULL REFERENCES firma(id),
    no TEXT DEFAULT '',
    mamul_id INTEGER NOT NULL REFERENCES mamul(id),
    miktar_kg REAL NOT NULL,
    baslangic TEXT DEFAULT '',
    bitis TEXT DEFAULT '',
    durum TEXT DEFAULT 'planlandi',    -- planlandi | uretimde | tamamlandi | iptal
    notlar TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS belge_dosya (
    id INTEGER PRIMARY KEY,
    firma_id INTEGER NOT NULL REFERENCES firma(id),
    belge_id INTEGER REFERENCES belge(id),
    dosya_adi TEXT NOT NULL,
    kategori TEXT DEFAULT 'diger',     -- beyanname | fatura | kapasite-raporu | basvuru | diger
    aciklama TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
"""

FIRMA = {
    "unvan": "MATEK KİMYA SAN. TİC. A.Ş.",
    "kisa_ad": "Matek Kimya",
    "vergi_no": "0300077479",
    "adres": "Fener Mah. Fener Kaynak Sk. No:3 Silivri / İstanbul",
}

ADMIN_USER = {"eposta": "admin@matek.com", "ad": "Matek Yönetici", "parola": "matek2026", "rol": "admin"}


def hash_password(parola: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    h = hashlib.scrypt(parola.encode(), salt=salt, n=2**14, r=8, p=1)
    return salt.hex() + "$" + h.hex()


def verify_password(parola: str, stored: str) -> bool:
    try:
        salt_hex, h_hex = stored.split("$")
        h = hashlib.scrypt(parola.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
        return secrets.compare_digest(h.hex(), h_hex)
    except Exception:
        return False


def canonical_hammadde(raw: str):
    s = raw.upper().replace("İ", "I").replace("Ş", "S").replace("Ü", "U").replace("Ö", "O").replace("Ç", "C").replace("Ğ", "G")
    s = re.sub(r"\s+", " ", s).strip()
    if "%99" in s:
        return "ETİL ALKOL %99"
    if "%96" in s:
        return "ETİL ALKOL %96"
    if "ISOPROPIL" in s or "ISOPORPIL" in s:
        return "İSOPROPİL ALKOL"
    if "METIL" in s:
        return "METİL ALKOL"
    if "BUTANOL" in s:
        return "BUTANOL"
    if "ETIL ASETAT" in s:
        return "ETİL ASETAT"
    if "MELAIK" in s or "MALEIK" in s:
        return "MALEİK REÇİNE"
    if "POLIAMID" in s or "POLYAMID" in s:
        return "POLİAMİD REÇİNE"
    if "NITRO" in s:
        return "NİTROSELÜLOZ REÇİNE"
    if "URETAN" in s:
        return "POLİÜRETAN REÇİNE"
    if "VAKS" in s:
        return "POLİETİLEN VAKS"
    if "KARBON" in s:
        return "KARBON KARASI"
    if "TITAN" in s:
        return "TİTANDİOKSİT"
    if "SIYAH" in s:
        return "KARBON KARASI"
    if "BEYAZ" in s:
        return "TİTANDİOKSİT"
    if "RENKLI" in s or "DIGER" in s or "PIGMENT" in s:
        return "PİGMENT"
    if "SEFFAF" in s:
        return None
    if "ETIL ALKOL" in s:
        return "ETİL ALKOL %99"
    return raw.strip()


HAMMADDE_CATALOG = [
    ("PİGMENT",             "32.04.17.00.00.11", 0),
    ("TİTANDİOKSİT",        "32.06.11.00.00.00", 0),
    ("KARBON KARASI",       "28.03.00.00.90.11", 0),
    ("NİTROSELÜLOZ REÇİNE", "39.12.20.19.00.11", 0),
    ("POLİÜRETAN REÇİNE",   "39.09.50.90.00.00", 0),
    ("POLİAMİD REÇİNE",     "39.08.90.00.00.00", 0),
    ("MALEİK REÇİNE",       "38.06.90.00.90.11", 0),
    ("ETİL ASETAT",         "29.15.31.00.00.00", 0),
    ("POLİETİLEN VAKS",     "34.04.90.00.19.00", 0),
    ("ETİL ALKOL %99",      "22.07.20.00.90.13", 1),
    ("ETİL ALKOL %96",      "22.07.20.00.90.13", 1),
    ("İSOPROPİL ALKOL",     "29.05.12.00.00.12", 1),
    ("METİL ALKOL",         "29.05.11.00.00.00", 1),
    ("BUTANOL",             "29.05.13.00.00.00", 1),
]


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrate(conn):
    """Var olan veritabanına geriye dönük kolon/tablo ekle (veri kaybı olmadan)."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(kullanici)")}
    for col, ddl in (("birim_id", "ALTER TABLE kullanici ADD COLUMN birim_id INTEGER REFERENCES birim(id)"),
                     ("unvan", "ALTER TABLE kullanici ADD COLUMN unvan TEXT DEFAULT ''"),
                     ("telefon", "ALTER TABLE kullanici ADD COLUMN telefon TEXT DEFAULT ''")):
        if col not in cols:
            conn.execute(ddl)
    # kalem düzeyi GTİP + resmi kalem no (beyanname/fatura satır numarası)
    for tablo in ("ithalat_kalem", "ihracat_kalem"):
        kcols = {r["name"] for r in conn.execute(f"PRAGMA table_info({tablo})")}
        if "gtip" not in kcols:
            conn.execute(f"ALTER TABLE {tablo} ADD COLUMN gtip TEXT DEFAULT ''")
        if "kalem_no" not in kcols:
            conn.execute(f"ALTER TABLE {tablo} ADD COLUMN kalem_no INTEGER")
    # varsayılan birimler
    firma = conn.execute("SELECT id FROM firma LIMIT 1").fetchone()
    if firma and conn.execute("SELECT COUNT(*) c FROM birim").fetchone()["c"] == 0:
        for ad in ("Dış Ticaret", "Muhasebe", "Üretim", "Yönetim"):
            conn.execute("INSERT OR IGNORE INTO birim (firma_id, ad) VALUES (?,?)", (firma["id"], ad))
    if firma:
        for ad in ("Depo", "Kalite Kontrol"):
            conn.execute("INSERT OR IGNORE INTO birim (firma_id, ad) VALUES (?,?)", (firma["id"], ad))
        _backfill_muhasebe(conn, firma["id"])


def _backfill_muhasebe(conn, firma_id):
    """Mevcut ithalat/ihracat kayıtlarından cari + fatura üret (idempotent)."""
    def cari_id_for(unvan, tip, ulke=""):
        unvan = (unvan or "").strip()
        if not unvan:
            return None
        row = conn.execute("SELECT id FROM cari WHERE firma_id=? AND unvan=?", (firma_id, unvan)).fetchone()
        if row:
            return row["id"]
        cur = conn.execute("INSERT INTO cari (firma_id, tip, unvan, ulke) VALUES (?,?,?,?)",
                           (firma_id, tip, unvan, ulke or ""))
        return cur.lastrowid

    for r in conn.execute(
        """SELECT i.* FROM ihracat i JOIN belge b ON b.id=i.belge_id
           WHERE b.firma_id=? AND NOT EXISTS
             (SELECT 1 FROM fatura f WHERE f.kaynak='ihracat' AND f.ref_id=i.id)""", (firma_id,)).fetchall():
        cid = cari_id_for(r["musteri"], "musteri", r["ulke"])
        conn.execute(
            """INSERT INTO fatura (firma_id, cari_id, tip, fatura_no, tarih, doviz, tutar, kaynak, ref_id, aciklama)
               VALUES (?,?,'satis',?,?,?,?,'ihracat',?,?)""",
            (firma_id, cid, r["fatura_no"], r["tarih"], r["doviz"], r["tutar"] or 0, r["id"],
             "İhracat kaydından otomatik"))

    for r in conn.execute(
        """SELECT i.* FROM ithalat i JOIN belge b ON b.id=i.belge_id
           WHERE b.firma_id=? AND NOT EXISTS
             (SELECT 1 FROM fatura f WHERE f.kaynak='ithalat' AND f.ref_id=i.id)""", (firma_id,)).fetchall():
        cid = cari_id_for(r["satici"], "tedarikci", r["mense"])
        conn.execute(
            """INSERT INTO fatura (firma_id, cari_id, tip, fatura_no, tarih, doviz, tutar, kaynak, ref_id, aciklama)
               VALUES (?,?,'alis',?,?,?,?,'ithalat',?,?)""",
            (firma_id, cid, r["fatura_no"] or r["beyanname_no"], r["tarih"], r["doviz"], r["tutar"] or 0, r["id"],
             "İthalat kaydından otomatik"))


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_conn()
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) c FROM firma").fetchone()["c"] == 0:
        _seed(conn)
    _migrate(conn)
    conn.commit()
    conn.close()


def _seed(conn):
    with open(SEED_PATH, encoding="utf-8") as f:
        seed = json.load(f)

    cur = conn.execute(
        "INSERT INTO firma (unvan, kisa_ad, vergi_no, adres) VALUES (?,?,?,?)",
        (FIRMA["unvan"], FIRMA["kisa_ad"], FIRMA["vergi_no"], FIRMA["adres"]))
    firma_id = cur.lastrowid

    conn.execute(
        "INSERT INTO kullanici (firma_id, eposta, ad, parola_hash, rol) VALUES (?,?,?,?,?)",
        (firma_id, ADMIN_USER["eposta"], ADMIN_USER["ad"], hash_password(ADMIN_USER["parola"]), ADMIN_USER["rol"]))

    b = seed["belge"]
    cur = conn.execute(
        "INSERT INTO belge (firma_id, belge_no, belge_tarihi, sure_sonu, ongorulen_ihracat_usd, ongorulen_ithalat_usd) VALUES (?,?,?,?,?,?)",
        (firma_id, b["belge_no"], b["belge_tarihi"], b["sure_sonu"], b["ongorulen_ihracat_usd"], b["ongorulen_ithalat_usd"]))
    belge_id = cur.lastrowid

    for ad, gtip, yerli in HAMMADDE_CATALOG:
        conn.execute("INSERT INTO hammadde (firma_id, ad, gtip, yerli) VALUES (?,?,?,?)", (firma_id, ad, gtip, yerli))

    for m in seed["mamuller"]:
        grup = m["satir_kodu"].split(".")[-1]
        conn.execute(
            "INSERT INTO mamul (belge_id, satir_kodu, grup, ad, gtip, taahhut_kg, birim_fiyat_usd) VALUES (?,?,?,?,?,?,?)",
            (belge_id, m["satir_kodu"], grup, m["ad"], m["gtip"], m["taahhut_kg"], m["birim_fiyat_usd"]))

    ham_ids = {r["ad"]: r["id"] for r in conn.execute("SELECT id, ad FROM hammadde WHERE firma_id=?", (firma_id,))}
    for mr in conn.execute("SELECT id, grup FROM mamul WHERE belge_id=?", (belge_id,)).fetchall():
        agg = {}
        for e in seed["recipes"].get(mr["grup"], []):
            if not e["katsayi"]:
                continue
            canon = canonical_hammadde(e["hammadde"])
            if not canon:
                continue
            if canon not in ham_ids:
                c2 = conn.execute("INSERT INTO hammadde (firma_id, ad) VALUES (?,?)", (firma_id, canon))
                ham_ids[canon] = c2.lastrowid
            agg[canon] = agg.get(canon, 0) + e["katsayi"]
        for canon, k in agg.items():
            conn.execute("INSERT OR REPLACE INTO recete (mamul_id, hammadde_id, katsayi) VALUES (?,?,?)",
                         (mr["id"], ham_ids[canon], k))
