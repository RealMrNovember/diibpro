<div align="center">

# 🏭 DİİBPro

**Fabrika Yönetim ve Dahilde İşleme (DİİB) Takip Sistemi**

*Fotoğrafını çek, belgen kendini yönetsin.*

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57?logo=sqlite&logoColor=white)](https://sqlite.org/)
[![Tesseract](https://img.shields.io/badge/OCR-Tesseract%205-blue)](https://github.com/tesseract-ocr/tesseract)
[![Claude](https://img.shields.io/badge/AI-Claude%20API-d97706)](https://platform.claude.com/)

[Canlı Demo](https://diibpro.cicibyte.com) · [Özellikler](#-özellikler) · [Kurulum](#-kurulum) · [Dağıtım](#-sunucuya-dağıtım) · [Mimari](#-mimari)

</div>

---

## 📌 Nedir?

**DİİBPro**, Dahilde İşleme Rejimi (DİR) kullanan üretici-ihracatçı firmalar için geliştirilmiş,
çok firmalı (multi-tenant) bir **fabrika yönetim ve DİİB taahhüt takip** platformudur.

Gümrük beyannamesi veya faturanın **fotoğrafını yükleyin** — sistem belgeyi okur (OCR ücretsiz,
AI opsiyonel), kalemleri DİİB satır kodlarına eşler, onayınızla stoğu ve ihracat taahhüdünü
otomatik günceller. Excel tablolarında elle sarf hesaplama dönemi biter.

> Türkiye pazarında "fotoğraftan belge okuma + otomatik sarf hesabı" sunan **ilk ve tek** çözümdür
> (Ağustos 2026 rakip analizi: `docs/pazar-arastirmasi.md`).

## ✨ Özellikler

### 📄 Dış Ticaret / DİİB
- 📷 **Fotoğraftan belge okuma** — JPG/PNG/PDF; motor seçimi:
  - **OCR** (varsayılan): Tesseract 5 + Türkçe dil paketi, tamamen yerel ve **ücretsiz**
  - **AI** (opsiyonel): Claude API ile daha isabetli okuma — yalnızca API anahtarı tanımlıysa
- ⚗️ **Otomatik sarf motoru** — kapasite raporu reçetelerine göre her ihracat kaleminden
  hammadde düşümü; tarih bazlı katsayılar, eşdeğer eşya bakiyeleri
- 🎯 **Canlı taahhüt takibi** — satır kodu bazında gerçekleşme %, kalan miktar, belge süresi
- 📑 **Excel benzeri kalem tabloları** — sıralama, sürükle-bırak sütun düzeni (kullanıcıya
  kayıtlı), sütun göster/gizle, satır düzenleme, CSV dışa aktarım, belge görseli indirme

### 🏭 Fabrika Modülleri
| Modül | İşlev |
|---|---|
| 🧾 **Muhasebe** | Cari hesaplar, alış-satış faturaları (ithalat/ihracattan **otomatik**), tahsilat/ödeme, açık bakiye |
| 📦 **Depo** | Hammadde + mamul stok kartları (DİİB hesabıyla birleşik), giriş/çıkış/sayım hareketleri |
| 🏗️ **Üretim** | İş emirleri; reçeteden hammadde ihtiyacı; tamamlanınca otomatik depo hareketleri |
| 🔬 **Kalite Kontrol** | Parti/numune test kayıtları (viskozite, renk, yoğunluk…), uygun/şartlı/red |
| 👥 **Yönetim** | Çalışan ekleme, roller (yönetici/operatör/izleyici), organizasyon birimleri |

### 🖥️ Platform
- **Showcase → Login → Uygulama** akışı; oturum çerezli kimlik doğrulama (scrypt)
- **Masaüstü** kenar menülü tam panel + **mobil** için ayrı kompakt görünüm (tek kod tabanı)
- Çok firmalı veri modeli — her müşteri firma kendi verisinde izole
- Excel geçmiş aktarımı (`backend/import_history.py`) — mevcut DİİB tablolarını tek komutla içeri alır

## 🚀 Kurulum

```bash
git clone https://github.com/RealMrNovember/diibpro.git
cd diibpro
python -m venv venv
venv/Scripts/activate          # Linux/macOS: source venv/bin/activate
pip install -r requirements.txt

# OCR motoru (opsiyonel ama önerilir)
winget install UB-Mannheim.TesseractOCR    # Ubuntu: apt install tesseract-ocr
# Türkçe dil paketi: data/tessdata/ altına tur.traineddata + eng.traineddata
# https://github.com/tesseract-ocr/tessdata_best

# AI motoru (opsiyonel)
cp .env.example .env           # ANTHROPIC_API_KEY gir

uvicorn backend.main:app --host 0.0.0.0 --port 8756 --app-dir .
```

`http://localhost:8756` → showcase · `/login` → giriş · `/app` → uygulama

İlk açılışta veritabanı tohum veriyle kurulur. Varsayılan yönetici hesabı `backend/db.py`
içinde tanımlıdır — **ilk girişten sonra parolayı mutlaka değiştirin**.

## 🌐 Sunucuya Dağıtım

Üretim kurulumu (Ubuntu + nginx + systemd):

```bash
# 1) Kod + venv
/www/wwwroot/ornek.com/app     # uygulama
/www/wwwroot/ornek.com/venv    # python ortamı

# 2) systemd servisi
[Service]
User=www
WorkingDirectory=/www/wwwroot/ornek.com/app
ExecStart=/www/wwwroot/ornek.com/venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8756
Restart=always

# 3) nginx reverse proxy
location / {
    proxy_pass http://127.0.0.1:8756;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}
client_max_body_size 50m;      # belge fotoğrafları için
```

> ⚠️ Cloudflare **Flexible SSL** arkasındaysanız origin'de http→https yönlendirmesi yapmayın
> (yönlendirme döngüsü oluşur). Full SSL modunda sorun yoktur.

## 🏗 Mimari

```
┌──────────── Frontend (vanilla JS, tek sayfa) ────────────┐
│  Showcase · Login · Panel · DİİB · Depo · Üretim         │
│  Kalite · Muhasebe · Yönetim · Profil                    │
└──────────────────────────┬───────────────────────────────┘
                           │ REST (JSON, oturum çerezi)
┌──────────────────────────▼───────────────────────────────┐
│                  FastAPI (backend/)                      │
│  main.py   → DİİB uçları, sayfalar, auth wiring          │
│  erp.py    → cari/fatura/ödeme, depo, üretim, kalite     │
│  auth.py   → oturum yönetimi (scrypt + HttpOnly çerez)   │
│  ocr.py    → Tesseract + alan ayrıştırıcı (regex/fuzzy)  │
│  extract.py→ Claude API (vision + structured outputs)    │
│  db.py     → şema, tohum, migrasyon, muhasebe backfill   │
└──────────────────────────┬───────────────────────────────┘
                           │
        SQLite (data/diib.db) · uploads/ (belge arşivi)
```

**Veri akışı:** Belge fotoğrafı → OCR/AI çıkarımı → kullanıcı onayı → kayıt
→ *ithalatta* stok ↑ + alış faturası → *ihracatta* reçete sarfı ↓ + taahhüt ↑ + satış faturası.

## 🗺 Yol Haritası

- [x] OCR + AI belge okuma, sarf motoru, taahhüt takibi
- [x] Fabrika modülleri (muhasebe, depo, üretim, kalite)
- [x] Excel benzeri kalem tabloları, kullanıcıya kayıtlı sütun düzeni
- [ ] KDV istisna listesi, TEV tablosu (EK-8), kapatma dosyası üretimi
- [ ] Uyarı motoru (süre sonu, taahhüt açığı, izin aşımı) + e-posta bildirim
- [ ] PostgreSQL + Docker Compose (SaaS ölçeklenme fazı)
- [ ] DYS XML/Excel içe aktarım, TCMB kur servisi
- [ ] Gümrük müşaviri paneli (çok firma görünümü)

Ayrıntılı SaaS kurgusu: [`docs/SAAS-MIMARI.md`](docs/SAAS-MIMARI.md) ·
Pazar analizi: [`docs/pazar-arastirmasi.md`](docs/pazar-arastirmasi.md)

## 📄 Lisans

© 2026 Cicibyte. Tüm hakları saklıdır — özel mülk (proprietary) yazılımdır;
izinsiz kopyalanamaz ve dağıtılamaz.
