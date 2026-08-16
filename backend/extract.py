# -*- coding: utf-8 -*-
"""Fatura / gümrük beyannamesi görsellerinden Claude API (vision + structured output) ile veri çıkarımı."""
import base64
import io
import json
import os

import anthropic

MODEL = "claude-opus-5"
MAX_TOKENS = 16000
MAX_EDGE = 2576  # yüksek çözünürlük vision sınırı; daha büyüğü token israfı

ITHALAT_SCHEMA = {
    "type": "object",
    "properties": {
        "belge_turu": {"type": "string", "enum": ["gumruk_beyannamesi", "fatura", "diger"]},
        "beyanname_no": {"type": "string", "description": "Gümrük beyannamesi tescil no, örn. 24343100IM00158701. Yoksa boş bırak."},
        "fatura_no": {"type": "string"},
        "tarih": {"type": "string", "description": "ISO format YYYY-MM-DD"},
        "gumruk": {"type": "string", "description": "Gümrük idaresi adı, örn. AMBARLI GÜMRÜK MÜDÜRLÜĞÜ"},
        "satici": {"type": "string", "description": "Satıcı / gönderici firma"},
        "mense": {"type": "string", "description": "Menşe ülke"},
        "doviz": {"type": "string", "description": "Para birimi: USD, EUR, TL"},
        "toplam_tutar": {"type": "number"},
        "kur": {"type": "number", "description": "Belgede yazan TCMB kuru, yoksa 0"},
        "kalemler": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "aciklama": {"type": "string", "description": "Belgede yazan mal tanımı"},
                    "hammadde": {
                        "type": "string",
                        "description": "Eşleşen kanonik hammadde adı; listeden seç. Emin değilsen en yakınını seç.",
                    },
                    "gtip": {"type": "string"},
                    "miktar_kg": {"type": "number"},
                    "birim_fiyat": {"type": "number"},
                    "tutar": {"type": "number"},
                },
                "required": ["aciklama", "hammadde", "gtip", "miktar_kg", "birim_fiyat", "tutar"],
                "additionalProperties": False,
            },
        },
        "guven_notu": {"type": "string", "description": "Okunamayan/şüpheli alanlar hakkında kısa Türkçe not"},
    },
    "required": ["belge_turu", "beyanname_no", "fatura_no", "tarih", "gumruk", "satici",
                 "mense", "doviz", "toplam_tutar", "kur", "kalemler", "guven_notu"],
    "additionalProperties": False,
}

IHRACAT_SCHEMA = {
    "type": "object",
    "properties": {
        "belge_turu": {"type": "string", "enum": ["fatura", "gumruk_beyannamesi", "diger"]},
        "fatura_no": {"type": "string", "description": "örn. IHR2024000000144"},
        "beyanname_no": {"type": "string", "description": "İhracat beyannamesi no, örn. 24411300EX00045288. Yoksa boş."},
        "tarih": {"type": "string", "description": "ISO format YYYY-MM-DD"},
        "musteri": {"type": "string"},
        "ulke": {"type": "string"},
        "doviz": {"type": "string"},
        "toplam_tutar": {"type": "number"},
        "kalemler": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "urun_adi": {"type": "string", "description": "Faturada yazan ürün adı, örn. SÜPERLAM BEYAZ"},
                    "satir_kodu": {
                        "type": "string",
                        "description": "Eşleşen DİİB satır kodu; listeden seç. Faturada yazıyorsa onu kullan; yoksa ürün cinsine (alkol bazı + renk) göre eşle.",
                    },
                    "miktar_kg": {"type": "number"},
                    "birim_fiyat": {"type": "number"},
                    "tutar": {"type": "number"},
                },
                "required": ["urun_adi", "satir_kodu", "miktar_kg", "birim_fiyat", "tutar"],
                "additionalProperties": False,
            },
        },
        "guven_notu": {"type": "string", "description": "Okunamayan/şüpheli alanlar hakkında kısa Türkçe not"},
    },
    "required": ["belge_turu", "fatura_no", "beyanname_no", "tarih", "musteri", "ulke",
                 "doviz", "toplam_tutar", "kalemler", "guven_notu"],
    "additionalProperties": False,
}


def _downscale(data: bytes, media_type: str):
    """Telefon fotoğraflarını 2576px uzun kenara küçült (token maliyeti için)."""
    try:
        from PIL import Image
    except ImportError:
        return data, media_type
    try:
        img = Image.open(io.BytesIO(data))
        if max(img.size) <= MAX_EDGE and len(data) < 4_000_000:
            return data, media_type
        img.thumbnail((MAX_EDGE, MAX_EDGE))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=88)
        return out.getvalue(), "image/jpeg"
    except Exception:
        return data, media_type


def _content_blocks(files):
    """files: [(bytes, media_type)] -> Claude içerik blokları (image/document)."""
    blocks = []
    for data, media_type in files:
        if media_type == "application/pdf":
            blocks.append({
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": base64.standard_b64encode(data).decode(),
                },
            })
        else:
            data, media_type = _downscale(data, media_type)
            blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64.standard_b64encode(data).decode(),
                },
            })
    return blocks


def _system_prompt(kind: str, hammaddeler, mamuller) -> str:
    if kind == "ithalat":
        katalog = "\n".join(f"- {h['ad']} (GTİP {h['gtip'] or '?'})" for h in hammaddeler)
        return f"""Sen AKKİM Matbaacılık'ın DİİB (Dahilde İşleme İzin Belgesi) takip sistemi için belge okuma asistanısın.
Sana bir İTHALAT belgesinin (gümrük giriş beyannamesi ve/veya ithalat faturası) fotoğrafları verilecek.
Görevin: belgedeki bilgileri eksiksiz çıkarmak ve her kalemi aşağıdaki kanonik hammadde kataloğundan birine eşlemek.

Kanonik hammadde kataloğu:
{katalog}

Kurallar:
- Miktarları KG cinsinden ver. Ton ise 1000 ile çarp.
- Tarihleri YYYY-MM-DD formatına çevir.
- Sayılarda Türkçe format olabilir (1.234,56 = 1234.56) — doğru yorumla.
- Aynı beyannamede birden çok kalem/renk dökümü olabilir (örn. RED 53.1 3000 Kg, YELLOW 13 5000 Kg) — hepsini ayrı kalem yap.
- Pigment renk dökümleri de PİGMENT hammaddesine eşlenir.
- Okuyamadığın alanı boş/0 bırak ve guven_notu alanında belirt. Asla uydurma."""
    else:
        satirlar = "\n".join(f"- {m['satir_kodu']}: {m['ad']} (GTİP {m['gtip']})" for m in mamuller)
        return f"""Sen AKKİM Matbaacılık'ın DİİB (Dahilde İşleme İzin Belgesi) takip sistemi için belge okuma asistanısın.
Sana bir İHRACAT belgesinin (ihracat faturası ve/veya gümrük çıkış beyannamesi) fotoğrafları verilecek.
Görevin: fatura kalemlerini çıkarmak ve her ürünü aşağıdaki DİİB satır kodlarından birine eşlemek.

DİİB satır kodları (mamul listesi):
{satirlar}

Eşleme mantığı (satır kodu faturada yazmıyorsa):
- Ürünün bazına bak (etil alkol / isopropil alkol / metil alkol bazlı) ve rengine bak (siyah / beyaz / şeffaf-vernik / diğer renkler).
- Örnek: "SÜPERLAM BEYAZ" etil alkol bazlıdır → ...008 (ETİL ALKOL BAZLI BEYAZ). "ISTAMPA SARI" metil alkol bazlıdır → ...010 (METİL BAZLI DİĞER). "ISTAMPA VERNİK" → ...012 (METİL BAZLI ŞEFFAF).
- Faturada "Bu ihracat ... DİİB kapsamındadır" ibaresi ve satır kodu yazıyorsa onu esas al.

Kurallar:
- Miktarları KG cinsinden ver.
- Tarihleri YYYY-MM-DD formatına çevir.
- Sayılarda Türkçe format olabilir (1.234,56 = 1234.56) — doğru yorumla.
- Okuyamadığın alanı boş/0 bırak ve guven_notu alanında belirt. Asla uydurma."""


def extract(kind: str, files, hammaddeler, mamuller) -> dict:
    """kind: 'ithalat' | 'ihracat'. files: [(bytes, media_type)]. Döndürür: şemaya uygun dict."""
    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY ortam değişkeninden
    schema = ITHALAT_SCHEMA if kind == "ithalat" else IHRACAT_SCHEMA
    system = _system_prompt(kind, hammaddeler, mamuller)
    content = _content_blocks(files)
    content.append({
        "type": "text",
        "text": "Bu belge(ler)deki bilgileri şemaya uygun şekilde çıkar.",
    })

    kwargs = dict(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": content}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
    )

    # Claude Opus 5: güvenlik sınıflandırıcısı nadiren reddedebilir — sunucu tarafı fallback açık
    try:
        response = client.beta.messages.create(
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            **kwargs,
        )
    except (anthropic.BadRequestError, TypeError):
        # eski SDK / beta reddi: normal yol
        response = client.messages.create(**kwargs)

    if response.stop_reason == "refusal":
        raise RuntimeError("Model belgeyi işlemeyi reddetti (güvenlik sınıflandırıcısı). Elle giriş yapın.")

    text = next((b.text for b in response.content if b.type == "text"), "")
    return json.loads(text)
