# -*- coding: utf-8 -*-
"""Yerel OCR (Tesseract) ile belge okuma — ücretsiz, çevrimdışı varsayılan motor.

Akış: görsel/PDF → ön işleme → Tesseract (tur+eng) → alan ayrıştırıcı (regex + desen eşleme)
→ AI motoruyla aynı taslak şeması. Ayrıştırılamayan alanlar boş bırakılır ve guven_notu'nda
listelenir; kullanıcı onay ekranında tamamlar.
"""
import difflib
import io
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESSDATA = os.path.join(BASE_DIR, "data", "tessdata")

_TESS_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    "/usr/bin/tesseract",
    "/usr/local/bin/tesseract",
    "tesseract",
]


def _find_tesseract():
    for p in _TESS_PATHS:
        if p == "tesseract" or os.path.exists(p):
            return p
    return None


def available() -> bool:
    return _find_tesseract() is not None


# ---------------------------------------------------------------- OCR çekirdeği
def _ocr_image(img) -> str:
    import pytesseract
    cmd = _find_tesseract()
    if not cmd:
        raise RuntimeError("Tesseract OCR kurulu değil. Kurulum: winget install UB-Mannheim.TesseractOCR")
    pytesseract.pytesseract.tesseract_cmd = cmd
    if os.path.exists(os.path.join(TESSDATA, "tur.traineddata")):
        os.environ["TESSDATA_PREFIX"] = TESSDATA
        lang = "tur+eng"
    else:
        lang = "eng"
    return pytesseract.image_to_string(img, lang=lang, config="--psm 6")


def _preprocess(data: bytes):
    from PIL import Image, ImageOps, ImageFilter
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    img = img.convert("L")                      # gri ton
    w, h = img.size
    if max(w, h) < 1800:                        # küçük fotoğrafı büyüt
        k = 1800 / max(w, h)
        img = img.resize((int(w * k), int(h * k)), Image.LANCZOS)
    img = ImageOps.autocontrast(img, cutoff=1)
    img = img.filter(ImageFilter.SHARPEN)
    return img


def _pdf_text(data: bytes) -> str:
    """PDF: önce metin katmanı; yoksa sayfaları görüntüye çevirip OCR."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
        if len(text.strip()) > 100:
            return text
    except Exception:
        pass
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf
    doc = pymupdf.open(stream=data, filetype="pdf")
    parts = []
    for page in doc:
        pix = page.get_pixmap(dpi=300)
        from PIL import Image
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("L")
        parts.append(_ocr_image(img))
    return "\n".join(parts)


def ocr_files(files) -> str:
    """files: [(bytes, media_type)] → birleşik ham metin."""
    parts = []
    for data, media_type in files:
        if media_type == "application/pdf":
            parts.append(_pdf_text(data))
        else:
            parts.append(_ocr_image(_preprocess(data)))
    return "\n".join(parts)


# ---------------------------------------------------------------- yardımcı ayrıştırıcılar
def _fix_codes(s: str) -> str:
    """Kod alanlarındaki tipik OCR karışıklıklarını düzelt (satır bazında değil, token bazında)."""
    return s


_RE_BEYANNAME = re.compile(r"\b(\d{8})\s?([I1l|]?[MX]|[IE][MX])\s?(\d{8})\b")
_RE_SATIR_KODU = re.compile(r"\b(\d{2})[.\s]([12])[.\s](\d{5})[.\s](\d{3})\b")
_RE_GTIP = re.compile(r"\b(\d{2})[.\s](\d{2})[.\s](\d{2})[.\s](\d{2})[.\s](\d{2})[.\s](\d{2})\b")
_RE_DATE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b")
_RE_QTY_KG = re.compile(r"([\d.]{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:,\d+)?)\s*(?:KG|Kg|kg|KİLOGRAM|KILOGRAM)")
_RE_FATURA = re.compile(r"\b([A-Z]{2,4}\s?20\d{2}\s?\d{9,12})\b")


def _tr_num(s: str):
    """Türkçe sayı formatı → float. '1.234,56' → 1234.56"""
    s = s.strip().replace(" ", "")
    if not s:
        return 0.0
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") == 1 and len(s.split(".")[1]) not in (3,):
        pass  # 12.5 gibi ondalık
    else:
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _find_beyanname(text: str, io_tag: str):
    """io_tag: 'IM' | 'EX'. OCR 1M/lM karışıklığını normalize eder."""
    for m in _RE_BEYANNAME.finditer(text):
        mid = m.group(2).upper().replace("1", "I").replace("L", "I").replace("|", "I")
        if len(mid) == 1:
            mid = "I" + mid
        if mid in ("IM", "EX") and mid == io_tag:
            return f"{m.group(1)}{mid}{m.group(3)}"
    # ikinci tur: etiket farkı gözetmeden ilkini al
    for m in _RE_BEYANNAME.finditer(text):
        mid = m.group(2).upper().replace("1", "I").replace("L", "I").replace("|", "I")
        if len(mid) == 1:
            mid = "I" + mid
        if mid in ("IM", "EX"):
            return f"{m.group(1)}{mid}{m.group(3)}"
    return ""


def _find_date(text: str) -> str:
    m = _RE_DATE.search(text)
    if not m:
        return ""
    d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
    if 1 <= d <= 31 and 1 <= mo <= 12:
        return f"{y}-{mo:02d}-{d:02d}"
    return ""


def _find_line_after(text: str, labels, max_len=60):
    """Etiket geçen satırda etiketten sonrasını, boşsa bir sonraki satırı döndür."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        up = line.upper()
        for lab in labels:
            idx = up.find(lab)
            if idx >= 0:
                rest = line[idx + len(lab):].strip(" :;.-\t")
                if len(rest) >= 3:
                    return rest[:max_len]
                if i + 1 < len(lines) and lines[i + 1].strip():
                    return lines[i + 1].strip()[:max_len]
    return ""


def _find_gumruk(text: str) -> str:
    m = re.search(r"([A-ZÇĞİÖŞÜa-zçğıöşü]+\s+GÜMRÜK\s+MÜDÜRLÜĞÜ)", text, re.IGNORECASE)
    return m.group(1).upper() if m else ""


def _find_doviz(text: str) -> str:
    up = text.upper()
    for tok, cur in (("USD", "USD"), ("EURO", "EUR"), ("EUR", "EUR"), ("AMERİKAN DOLARI", "USD"), ("TRY", "TL")):
        if tok in up:
            return cur
    return ""


def _simplify(s: str) -> str:
    tr = str.maketrans("İIŞÇÖÜĞıişçöüğ", "IISCOUGIISCOUG")
    return re.sub(r"[^A-Z0-9 ]", "", s.upper().translate(tr))


def _fuzzy_find(line: str, names: dict, threshold=0.72):
    """Satırda katalog adı ara. names: {simplified_name: orijinal_kayıt}"""
    sline = _simplify(line)
    if not sline:
        return None
    best, best_r = None, 0.0
    for sname, rec in names.items():
        if sname in sline:
            return rec
        # kelime pencere benzerliği
        r = difflib.SequenceMatcher(None, sname, sline).ratio()
        if r > best_r:
            best, best_r = rec, r
    return best if best_r >= threshold else None


# ---------------------------------------------------------------- ana ayrıştırıcılar
def parse_ithalat(text: str, hammaddeler) -> dict:
    missing = []
    names = {_simplify(h["ad"]): h for h in hammaddeler}
    # alternatif adlar
    alias = {
        "PIGMENT": "PİGMENT", "TITAN DIOKSIT": "TİTANDİOKSİT", "TITANDIOKSIT": "TİTANDİOKSİT",
        "NITROSELULOZ RECINE": "NİTROSELÜLOZ REÇİNE", "NITROSELULOZ": "NİTROSELÜLOZ REÇİNE",
        "POLIURETAN RECINE": "POLİÜRETAN REÇİNE", "POLIAMID RECINE": "POLİAMİD REÇİNE",
        "MALEIK RECINE": "MALEİK REÇİNE", "MELAIK RECINE": "MALEİK REÇİNE",
        "KARBON KARASI": "KARBON KARASI", "ETIL ASETAT": "ETİL ASETAT",
    }
    by_ad = {h["ad"]: h for h in hammaddeler}
    for k, v in alias.items():
        if v in by_ad:
            names.setdefault(_simplify(k), by_ad[v])

    kalemler = []
    for line in text.splitlines():
        if not line.strip():
            continue
        rec = _fuzzy_find(line, names)
        qm = _RE_QTY_KG.search(line)
        if rec and qm:
            qty = _tr_num(qm.group(1))
            if qty <= 0:
                continue
            nums = [_tr_num(x) for x in re.findall(r"[\d.]+,\d+|\d+[.,]\d+", line)]
            bf = next((n for n in nums if 0.1 < n < 100 and n != qty), 0)
            kalemler.append({
                "aciklama": line.strip()[:80],
                "hammadde": rec["ad"],
                "gtip": rec.get("gtip") or "",
                "miktar_kg": qty,
                "birim_fiyat": bf,
                "tutar": round(qty * bf, 2) if bf else 0,
            })
    if not kalemler:
        missing.append("kalemler (hammadde satırı bulunamadı — elle ekleyin)")

    fat = _RE_FATURA.search(text)
    out = {
        "belge_turu": "gumruk_beyannamesi" if "BEYANNAME" in text.upper() else "fatura",
        "beyanname_no": _find_beyanname(text, "IM"),
        "fatura_no": fat.group(1).replace(" ", "") if fat else "",
        "tarih": _find_date(text),
        "gumruk": _find_gumruk(text),
        "satici": _find_line_after(text, ["GÖNDERİCİ", "GONDERICI", "SATICI", "İHRACATÇI", "IHRACATCI", "EXPORTER", "SELLER"]),
        "mense": _find_line_after(text, ["MENŞE", "MENSE", "ORIGIN"], max_len=25),
        "doviz": _find_doviz(text) or "USD",
        "toplam_tutar": 0,
        "kur": 0,
        "kalemler": kalemler,
        "guven_notu": "",
    }
    for f, lab in (("beyanname_no", "beyanname no"), ("tarih", "tarih"), ("gumruk", "gümrük"), ("satici", "satıcı")):
        if not out[f]:
            missing.append(lab)
    out["guven_notu"] = ("OCR ile okundu. Bulunamayan alanlar: " + ", ".join(missing)) if missing else "OCR ile okundu — tüm alanları kontrol edin."
    return out


# ürün adı ipuçlarından grup tahmini (satır kodu son 3 hane)
_GRUP_KURALLARI = [
    (("ISTAMPA", "SIYAH"), "009"), (("ISTAMPA", "BEYAZ"), "011"), (("ISTAMPA", "WHITE"), "011"),
    (("ISTAMPA", "VERNIK"), "012"), (("ISTAMPA", "SEFFAF"), "012"), (("ISTAMPA",), "010"),
    (("FLEXOLIN", "SIYAH"), "001"), (("FLEXOLIN", "BEYAZ"), "003"), (("FLEXOLIN",), "002"),
    (("LAK",), "013"), (("TINER",), "015"), (("THINNER",), "015"), (("INCELTICI",), "015"),
    (("VERNIK",), "006"), (("SEFFAF",), "006"), (("VERSCHNITT",), "006"),
    (("BEYAZ",), "008"), (("WHITE",), "008"), (("SIYAH",), "005"), (("BLACK",), "005"),
]


def _guess_satir_kodu(urun: str, mamuller):
    s = _simplify(urun)
    for keys, grup in _GRUP_KURALLARI:
        if all(k in s for k in keys):
            m = next((m for m in mamuller if m["satir_kodu"].endswith("." + grup)), None)
            if m:
                return m["satir_kodu"]
    # varsayılan: etil alkol bazlı diğer (007) — en büyük taahhüt kalemi renklilerdir
    m = next((m for m in mamuller if m["satir_kodu"].endswith(".007")), None)
    return m["satir_kodu"] if m else ""


def parse_ihracat(text: str, mamuller) -> dict:
    missing = []
    lines = text.splitlines()
    kalemler = []
    kodlar_metinde = _RE_SATIR_KODU.findall(text)

    for line in lines:
        qm = _RE_QTY_KG.search(line)
        if not qm:
            continue
        qty = _tr_num(qm.group(1))
        if qty <= 0 or qty > 500000:
            continue
        skm = _RE_SATIR_KODU.search(line)
        satir_kodu = ".".join(skm.groups()) if skm else ""
        # satır kodunu metinden çıkar ki ürün adına ve fiyat aramaya karışmasın
        clean_line = _RE_SATIR_KODU.sub(" ", line)
        qm2 = _RE_QTY_KG.search(clean_line) or qm
        # ürün adı: satırda miktardan önceki metin
        urun = clean_line[:qm2.start()].strip(" -:;\t")
        urun = re.sub(r"^\d+[\s.)-]*", "", urun).strip()[:60]
        if len(_simplify(urun)) < 3:
            continue
        if not satir_kodu:
            satir_kodu = _guess_satir_kodu(urun, mamuller)
        tail = _RE_DATE.sub(" ", clean_line[qm2.end():])
        nums = [_tr_num(x) for x in re.findall(r"\d+,\d+|\d+\.\d{1,2}\b", tail)]
        bf = next((n for n in nums if 0.05 < n < 100 and n != qty), 0)
        kalemler.append({
            "urun_adi": urun,
            "satir_kodu": satir_kodu,
            "miktar_kg": qty,
            "birim_fiyat": bf,
            "tutar": round(qty * bf, 2) if bf else 0,
        })

    if not kalemler:
        missing.append("kalemler (ürün satırı bulunamadı — elle ekleyin)")

    fat = _RE_FATURA.search(text)
    out = {
        "belge_turu": "fatura" if "FATURA" in text.upper() or "INVOICE" in text.upper() else "gumruk_beyannamesi",
        "fatura_no": fat.group(1).replace(" ", "") if fat else "",
        "beyanname_no": _find_beyanname(text, "EX"),
        "tarih": _find_date(text),
        "musteri": _find_line_after(text, ["ALICI", "MÜŞTERİ", "MUSTERI", "CONSIGNEE", "BUYER", "SAYIN"]),
        "ulke": _find_line_after(text, ["ÜLKE", "ULKE", "COUNTRY", "VARIŞ", "VARIS"], max_len=25),
        "doviz": _find_doviz(text) or "USD",
        "toplam_tutar": 0,
        "kalemler": kalemler,
        "guven_notu": "",
    }
    for f, lab in (("fatura_no", "fatura no"), ("tarih", "tarih"), ("musteri", "müşteri")):
        if not out[f]:
            missing.append(lab)
    note = "OCR ile okundu."
    if not kodlar_metinde and kalemler:
        note += " Satır kodları belgede bulunamadı, ürün adından tahmin edildi — kontrol edin."
    if missing:
        note += " Bulunamayan alanlar: " + ", ".join(missing)
    out["guven_notu"] = note
    return out


def extract(kind: str, files, hammaddeler, mamuller) -> dict:
    text = ocr_files(files)
    if len(text.strip()) < 20:
        raise RuntimeError("OCR belgede okunabilir metin bulamadı. Daha net bir fotoğraf deneyin veya AI motorunu kullanın.")
    result = parse_ithalat(text, hammaddeler) if kind == "ithalat" else parse_ihracat(text, mamuller)
    result["_ocr_text"] = text[:4000]  # hata ayıklama / kullanıcı kontrolü için
    return result
