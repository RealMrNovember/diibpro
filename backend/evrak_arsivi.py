# -*- coding: utf-8 -*-
"""Geçmiş evrakları (DİİB klasörü) sistem arşivine alır: uploads/arsiv/ + belge_dosya kayıtları.

Çalıştırma:  python -m backend.evrak_arsivi ["kaynak klasör"]
İdempotent: aynı dosya adı tekrar eklenmez. Kişisel veri içeren kimlik belgeleri KVKK
gereği bilinçli olarak HARİÇ tutulur.
"""
import os
import shutil
import sys
import unicodedata

from . import db as dbm

ARSIV_DIR = os.path.join(dbm.BASE_DIR, "uploads", "arsiv")

# (dosya adı deseni [küçük harf, geçen], kategori, açıklama)
KATALOG = [
    ("kapasite raporu son", "kapasite-raporu", "Kapasite raporu (29.11.2021 — güncel)"),
    ("kapasite raporu (yenilendi)", "kapasite-raporu", "Kapasite raporu (23.11.2021 revizyonu)"),
    ("kapasite raporu güncel", "kapasite-raporu", "Kapasite raporu (önceki sürüm)"),
    ("kapasite raporu 26.09", "kapasite-raporu", "Kapasite raporu (26.09.2021)"),
    ("kapasite_raporu_muracaat", "basvuru", "Kapasite raporu müracaat formu"),
    ("akkim ltd..pdf", "resmi-belge", "Vergi levhası (Ltd. Şti.)"),
    ("akkim mürekkep a.ş", "resmi-belge", "Vergi levhası (A.Ş.)"),
    ("imza sirkuleri", "resmi-belge", "İmza sirküleri (noter onaylı)"),
    ("ito.pdf", "resmi-belge", "Ticaret sicil gazetesi (sermaye artırımı)"),
    ("kopya sgk", "resmi-belge", "SGK bildirimleri listesi"),
    ("diib belge giriş dilekçesi", "basvuru", "DİİB üretim tespit / evrak giriş dilekçesi"),
    ("belge ve ekleri", "belge-bilgi", "DYS belge ve ekleri ekran görüntüleri"),
    ("diib bilgilendirme metni.png", "belge-bilgi", "DYS belge değerlendirme bilgileri"),
    ("diib bilgilendirme metni notlari", "belge-bilgi", "DYS özel şartlar (madde 137/93)"),
    ("diib ital teşvik listesi", "basvuru", "İthalat teşvik listesi (2021 belgesi)"),
    ("istanbul maden", "basvuru", "İMMİB dilekçesi (kapasite raporu güncelleme)"),
    ("diib takip listesi", "calisma-dosyasi", "DİİB takip listesi şablonu (boş)"),
    ("son durum", "calisma-dosyasi", "Hammadde alım durumu (31.08.2022)"),
    ("gümrük takip listesi", "calisma-dosyasi", "Gümrük otomasyon beyanname dökümü"),
    ("faturada kullanilacak", "belge-bilgi", "Faturada kullanılacak ürün tanımları"),
    ("ek süre ve alimlar", "calisma-dosyasi", "Ek süre ve alım durumu raporu"),
    ("mevcut kapasiteye göre", "calisma-dosyasi", "Önceki belge hesap çalışması"),
    ("kapasite formülasyonuna", "calisma-dosyasi", "Kapasite formülasyon çalışması"),
    ("revize", "calisma-dosyasi", "Belge revize çalışması"),
    ("revizyon", "calisma-dosyasi", "Belge revizyon çalışması"),
    ("hesapama tablosu", "calisma-dosyasi", "Kapasite reçeteleri hesap tablosu"),
    ("ürün azlı çalışma", "calisma-dosyasi", "Kapasite raporu ürün çalışması"),
    ("diib-4", "kaynak-veri", "DİİB-4 ithalat-ihracat sarf tabloları (ana kaynak Excel)"),
]

# KVKK: kişisel veri içerenler arşive alınmaz
HARIC = ["kimlik", "img-2021", "nüfus"]


def _fold(s: str) -> str:
    """Türkçe İ/ı dahil güvenli küçük harf karşılaştırma (birleşik işaretleri at)."""
    s = s.replace("İ", "i").replace("I", "i").replace("ı", "i")
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _kategori(fname: str):
    f = _fold(fname)
    if any(_fold(h) in f for h in HARIC):
        return None, None
    for desen, kat, acik in KATALOG:
        if _fold(desen) in f:
            return kat, acik
    return "diger", ""


def _safe_name(fname: str) -> str:
    """Türkçe karakterleri koru ama dosya sistemine güvenli hale getir."""
    s = unicodedata.normalize("NFC", fname)
    return s.replace("/", "-").replace("\\", "-")


def run(kaynak: str | None = None):
    dbm.init_db()
    root = os.path.dirname(dbm.BASE_DIR)
    kaynaklar = [kaynak] if kaynak else [os.path.join(root, "DİİB"), root]
    os.makedirs(ARSIV_DIR, exist_ok=True)

    conn = dbm.get_conn()
    firma = conn.execute("SELECT id FROM firma LIMIT 1").fetchone()
    belge = conn.execute("SELECT id FROM belge LIMIT 1").fetchone()
    mevcut = {r["dosya_adi"] for r in conn.execute("SELECT dosya_adi FROM belge_dosya")}

    eklendi, atlandi = 0, 0
    for kdir in kaynaklar:
        if not os.path.isdir(kdir):
            continue
        for dirpath, _dirs, files in os.walk(kdir):
            if "akkim-diib-app" in dirpath:
                continue
            for f in files:
                if not f.lower().endswith((".pdf", ".docx", ".xlsx", ".xls", ".xlsm", ".png", ".jpg", ".jpeg")):
                    continue
                kat, acik = _kategori(f)
                if kat is None:
                    atlandi += 1
                    continue
                safe = _safe_name(f)
                if safe in mevcut:
                    continue
                hedef = os.path.join(ARSIV_DIR, safe)
                if not os.path.exists(hedef):
                    try:
                        shutil.copy2(os.path.join(dirpath, f), hedef)
                    except OSError:
                        continue
                conn.execute(
                    "INSERT INTO belge_dosya (firma_id, belge_id, dosya_adi, kategori, aciklama) VALUES (?,?,?,?,?)",
                    (firma["id"], belge["id"] if belge else None, safe, kat, acik))
                mevcut.add(safe)
                eklendi += 1
            if kdir == root:
                break  # kökte alt klasörlere inme (yalnız ana Excel)
    conn.commit()
    conn.close()
    return {"eklendi": eklendi, "kvkk_haric": atlandi}


if __name__ == "__main__":
    print(run(sys.argv[1] if len(sys.argv) > 1 else None))
