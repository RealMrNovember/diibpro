# DİİB Takip — SaaS Ürün Kurgusu ve Teknik Mimari

> Durum: Taslak v1 — 16.08.2026. Local MVP (`akkim-diib-app/`) çalışır durumda; bu doküman
> ürünün çok kiracılı (multi-tenant) SaaS'a evrim planıdır. Pazar analizi bölümü rakip
> araştırması tamamlandığında güncellenir.

---

## 1. Ürün Vizyonu

**"Fotoğrafını çek, DİİB'in kendini yönetsin."**

Dahilde işleme rejimi kullanan üretici-ihracatçılar için; gümrük beyannamesi ve fatura
görsellerinden yapay zekâ ile veri çıkaran, sarf/reçete hesabını, taahhüt gerçekleşmesini,
stok bakiyesini ve kapatma hazırlığını otomatikleştiren web tabanlı SaaS.

Hedef kullanıcı profili:
- Birincil: KOBİ ölçekli üretici-ihracatçının dış ticaret/muhasebe sorumlusu (bugün Excel kullanan)
- İkincil: Gümrük müşavirleri (çok müşterili görünüm), YMM/SMMM'ler (KDV istisna listeleri)

Temel değer önerileri:
1. **AI belge okuma** — beyanname/fatura fotoğrafı → yapılandırılmış kayıt (dakikalar yerine saniyeler)
2. **Otomatik sarf muhasebesi** — kapasite raporu reçetesine göre hammadde düşümü, renk formülü dağıtımı
3. **Canlı taahhüt panosu** — belge kapanmadan önce riski görme (süre, miktar, değer, döviz kullanım oranı)
4. **Kapatma dosyası üretimi** — EK listeler, KDV istisna listesi, TEV tablosu, kapanış dilekçesi çıktıları

## 2. Modül Haritası

| # | Modül | MVP'de | SaaS v1 | Sonrası |
|---|-------|:------:|:-------:|:-------:|
| 1 | Belge yönetimi (DİİB kartı, satır kodları, revizeler, ek süre) | kısmi | ✅ | |
| 2 | AI belge okuma (fatura, beyanname; görsel + PDF) | ✅ | ✅ | e-Fatura XML |
| 3 | İthalat kayıtları + teminat mektubu takibi | kısmi | ✅ | |
| 4 | İhracat kayıtları + aylık özetler | ✅ | ✅ | |
| 5 | Reçete/sarf motoru (katsayı, eşdeğer eşya, renk formülleri, FIFO) | kısmi | ✅ | |
| 6 | Stok ve bakiye panosu | ✅ | ✅ | |
| 7 | Uyarı motoru (süre sonu, taahhüt açığı, izin aşımı, eksi stok) | — | ✅ | e-posta/WhatsApp |
| 8 | Raporlar: KDV istisna listesi, TEV tablosu (EK-8), kapatma seti | — | ✅ | |
| 9 | Çok kiracılılık, kullanıcı/rol, denetim izi | — | ✅ | |
| 10 | Gümrük müşaviri paneli (çok firma) | — | — | ✅ |
| 11 | Entegrasyonlar: BİLGE/tek pencere dışa aktarımları, ERP/muhasebe | — | — | ✅ |

## 3. SaaS Mimarisi

### 3.1 Teknoloji seçimi

| Katman | Seçim | Gerekçe |
|---|---|---|
| API | **FastAPI (Python)** | MVP ile süreklilik; async; Pydantic doğrulama; AI SDK'ları Python'da olgun |
| Veritabanı | **PostgreSQL** (tenant_id ile satır düzeyi ayrım + RLS) | Tek küme, düşük maliyet, kolay yedekleme; RLS ile kiracı izolasyonu garanti |
| ORM/Migrasyon | SQLAlchemy 2 + Alembic | Şema evrimi güvenli |
| Kimlik | JWT (access+refresh) + bcrypt; e-posta doğrulama; TOTP 2FA (opsiyonel) | Standart, bağımlılık az |
| Dosya depolama | S3 uyumlu (MinIO self-host / bulut S3) | Belge arşivi yasal saklama (10 yıl) |
| AI çıkarım | Anthropic Claude API (`claude-opus-5`), yapılandırılmış çıktı şemaları | MVP'de kanıtlandı |
| Kuyruk | İlk fazda gerek yok (senkron çıkarım ~10-30 sn); ölçekte Redis + arq/Celery | Basit başla |
| Frontend | SaaS v1'de **React (Vite) + TypeScript**, mobil öncelikli PWA | Form yoğunluğu artınca vanilla JS sürdürülemez |
| Sunum | Docker Compose (API + Postgres + MinIO + Caddy/Traefik TLS) | Kullanıcının hazırladığı sunucuya tek komut kurulum |
| İzleme | Sentry (hata) + basit audit log tablosu | |

### 3.2 Çok kiracılı veri modeli (çekirdek)

```
tenant (firma)          user (kullanıcı, rol: admin/operator/viewer, tenant_id)
  └── belge (DİİB kartı: no, tarih, süre, öngörülen $, durum, revizyonlar)
        ├── belge_ithalat_satiri (satır kodu, GTİP, madde, izin kg, izin $)
        ├── belge_ihracat_satiri (satır kodu, GTİP, mamul, taahhüt kg, birim fiyat)
        ├── recete (ihracat satırı × hammadde → katsayı; tarih aralıklı versiyon*)
        ├── ithalat (beyanname) ── ithalat_kalem (satır kodu eşleşmeli, kg, kıymet, kur)
        │      └── teminat (banka, tutar, çözülme)
        ├── ihracat (fatura+beyanname) ── ihracat_kalem (satır kodu, kg, tutar)
        ├── belge_dosya (S3 anahtarı, tür: beyanname/fatura/kapasite raporu…)
        └── audit_log (kim, ne, ne zaman, eski→yeni)
```

\* Reçete versiyonlama önemli: Excel'de görüldü — "POLİÜRETAN REÇİNE 14.10.2024 SONRASI" gibi
tarih bazlı katsayı değişimleri oluyor. `recete(gecerli_baslangic, gecerli_bitis)` alanlarıyla
ihracat tarihine göre doğru katsayı seçilir.

Kiracı izolasyonu: her tabloda `tenant_id`; PostgreSQL **Row Level Security** ile
`current_setting('app.tenant_id')` filtresi; API katmanında JWT'den tenant bağlama.
Yanlışlıkla sızıntı iki katmanda da engellenir.

### 3.3 AI çıkarım hattı (üretim sürümü)

1. Yükleme → S3'e yaz, `belge_dosya` kaydı (arşiv + yasal saklama)
2. Görsel ön işleme: 2576px'e küçült, PDF ise sayfaları ayır
3. Claude çağrısı: kiracının **kendi satır kodu/reçete kataloğu** system prompt'a gömülür
   (prompt caching ile maliyet düşer); yapılandırılmış çıktı şeması zorlanır
4. Güven kontrolü: model `guven_notu` alanına şüpheli alanları yazar; toplamlar çapraz
   doğrulanır (kalem toplamı ≈ fatura toplamı, kg tutarlılığı)
5. Taslak kayıt → kullanıcı onay ekranı (düzelt-onayla) → işleme
6. Geri bildirim döngüsü: kullanıcının düzelttiği alanlar loglanır → prompt iyileştirme verisi

Maliyet notu: fotoğraf başına ~1.500-4.800 görsel token + katalog. Kiracı başına aylık belge
adedi sınırlı (tipik 10-60 beyanname/ay) → AI maliyeti abonelik içinde rahat karşılanır.

### 3.4 Uyarı motoru (SaaS v1)

Günlük zamanlanmış iş; kural örnekleri:
- Belge süresi sonuna ≤ 60/30/7 gün kala + taahhüt gerçekleşme < eşik → uyarı
- Hammadde ithalatı izin miktarını aşıyor → engel/uyarı
- Sarf, ithal edilen miktarı aştı (eşdeğer eşya bakiyesi eksi) → bilgi
- Döviz kullanım oranı (ithalat$/ihracat$) belge sınırına yaklaşıyor → uyarı
- Açık (kapanmamış) ihracat beyannamesi ≥ X gün → hatırlatma

### 3.5 Raporlama (SaaS v1)

Excel'deki karşılıkları birebir üretilecek çıktılar (XLSX/PDF):
- İthalat listesi + İhracat listesi (belge formatında, aylık ara toplamlı)
- Sarf tablosu (fatura kalemi × hammadde matrisi — bugünkü "İHR.FAT. SARF")
- **KDV istisna listesi** (maliye formatı: ihraç ürün içindeki DİİB'li girdi + tutar)
- **TEV tablosu (EK-8)**: ihracat-ithalat eşleştirme, %oran, kur, ödenecek TEV
- **Kapatma seti**: taahhüt hesabı, kapanış dilekçesi, hakediş özetleri

### 3.6 Güvenlik ve uyum

- TLS zorunlu; parola bcrypt; oturum JWT kısa ömür + refresh rotasyonu
- Rol bazlı yetki: admin (tanım+kullanıcı), operator (kayıt), viewer (rapor)
- KVKK: kişisel veri minimal (kullanıcı e-postası); belge görselleri ticari sır → kiracı bazlı
  şifreli bucket, erişim loglu
- Denetim izi: tüm yazma işlemleri audit_log'a; kayıt silme yerine "iptal" (soft delete)
- Yedekleme: Postgres günlük dump + S3 versiyonlama

## 4. Yol Haritası

| Faz | Kapsam | Süre tahmini |
|---|---|---|
| **F0 — Local MVP** ✅ | Fotoğraf→çıkarım→stok/taahhüt; tek firma; Akkim gerçek verisiyle saha testi | tamam |
| **F1 — Sertleştirme** | Auth (JWT), çoklu belge, belge kartı yönetimi, PostgreSQL'e geçiş, Docker Compose, audit log | 2-3 hafta |
| **F2 — SaaS v1** | Multi-tenant + RLS, React arayüz, uyarı motoru, KDV/TEV/kapatma raporları, S3 arşiv, faturalama (Stripe/iyzico abonelik) | 6-8 hafta |
| **F3 — Büyüme** | Gümrük müşaviri paneli, e-Fatura XML alımı, ERP entegrasyonları, WhatsApp bildirim, çok dil | talebe göre |

Fiyatlandırma iskeleti (pazar araştırmasıyla netleşecek):
- **Başlangıç**: tek belge, 2 kullanıcı, AI okuma kotalı — aylık abonelik
- **Profesyonel**: sınırsız belge, 5+ kullanıcı, raporlar, uyarılar
- **Müşavir**: çok firma yönetimi, firma başına fiyat

## 5. Pazar Analizi (16.08.2026 web araştırması)

### 5.1 Rakip haritası

Pazar iki katmandan oluşuyor; **sanayici odaklı bağımsız DİİB SaaS'ı fiilen boş**:

| Firma / Ürün | Konum | DİİB yetkinliği | Model | Fiyat |
|---|---|---|---|---|
| **Evrim Yazılım — DİİB Modülü** (pazar lideri) | Gümrük müşavirliği ekosistemi | DYS XML/Excel içe aktarım, müşavirden anlık beyanname akışı, ihracatta en uygun ithalat dosyasından otomatik düşüm, tescil öncesi TEV hesaplama | Kurumsal platform | Teklif usulü (ücretleri İGMD yazışmasına konu olacak kadar tartışmalı) |
| **Mavi Bilişim — Mavi Gümrük** | Müşavir yazılımı | "Düşümlü Belge Takip": dahilde işleme düşümleri, tescil öncesi aşım kontrolü, BİLGE/EDI, TEV | On-prem + bulut, yıllık lisans | Teklif usulü |
| **Bilgin Yazılım** | Müşavir yazılımı | Beyanname/EDI odaklı; DİİB'e özel modül belirsiz | On-prem | Teklif usulü |
| **ATEZ** | AI beyanname kontrol (müşavir tarafı) | DİİB kapatma modülü doğrulanamadı | Kurumsal SaaS | Teklif usulü |
| **Sighthem** | Dış ticaret SaaS (tek modern SaaS örneği) | DİİB operasyon takibi, kalan taahhüt/süre uyarıları; TEV/kapatma derinliği kanıtlanmamış; OCR'ı yalnız kartvizit | Self-servis SaaS | "Şeffaf fiyat" iddiası |
| **Logo Netsis / DİA / SOFT** | ERP dış ticaret modülleri | DİİB yan modül; reçete/sarf derinliği sınırlı | ERP lisans/bulut | Bayi kanalı |
| **ÜNSPED MÇP** | Müşavirlik hizmet portalı | DİİB takibi hizmet olarak (yazılım ürünü değil) | Hizmete bağlı | Sözleşme |

Aranıp **bulunamayanlar**: NetBT, Bilgeport, "Trade Vision" (yazılım olarak), Doğruer'in bağımsız DİİB ürünü.

### 5.2 Sektör standardı özellikler (olmazsa olmaz seti)

1. Satır kodu bazında taahhüt düşümü + döviz kullanım oranı
2. Süre/ek süre uyarıları
3. Sarf-reçete hesabı (fire, ikincil işlem görmüş ürün dahil)
4. Beyanname verisi alımı (BİLGE/EDI veya müşavirden) + tescil öncesi aşım kontrolü
5. **DYS entegrasyonu**: 19.09.2022'den beri tüm DİR işlemleri DYS üzerinden; yazılımlar DYS'nin
   belge XML'i ve sarfiyat Excel'ini **indir-yükle** yöntemiyle alıyor (canlı API sunan yok)
6. TEV hesaplama (AB ihracatında 3. ülke girdisi)
7. Kapatma dosyası üretimi (YMM raporuna altlık listeler)
8. KDV tecil-terkin listeleri (pazarda zayıf — kısmi boşluk)

### 5.3 Farklılaşma fırsatları (bu ürünün konumu)

1. **AI belge okuma → otomatik sarf: doğrudan rakip YOK.** "Fotoğraf yükle → kalemler ayrışsın →
   reçeteye göre düşüm otomatik" akışını sunan tek ürün bulunamadı. Bu, ürünün ana farkıdır ve
   MVP'de kanıtlanmıştır.
2. **Sanayici self-servis SaaS boşluğu**: mevcutlar müşavir eklentisi ya da ERP modülü; belge
   sahibi KOBİ'nin kurulumsuz, mobil, kendi başına kullanacağı ürün pratikte yok.
3. **Şeffaf abonelik fiyatı**: pazarın tamamı "teklif al"; açık fiyat sayfası tek başına farklılaştırıcı.
4. **DYS dosya akışını kolaylaştırma**: DYS XML/Excel sürükle-bırak içe aktarım + tek tık kapatma seti.
5. **Kimya/mürekkep dikeyi**: renk formülü dağıtımı, çözücü/fire mantığı gibi karmaşık reçeteler —
   Akkim verisiyle doğrulanmış hazır şablonlar.

### 5.4 Riskler

- **Evrim'in şebeke etkisi**: müşavir ağından anlık beyanname akışı. Karşı hamle: veri girişini
  müşavire bağımlı olmaktan çıkaran OCR/fotoğraf kanalı (bu ürünün özü) + DYS dosya alımı.
- **Mevzuat derinliği**: TEV ve kapatma hesabında hata mali sonuç doğurur → raporlar "müşavir
  onayına hazır taslak" olarak konumlanmalı; hesap varsayımları ekranda şeffaf gösterilmeli.
- Kaynak URL listesi: `docs/pazar-arastirmasi.md`

## 6. MVP → SaaS Geçiş Notları (teknik borç listesi)

- SQLite → PostgreSQL: SQL'ler ANSI'ye yakın tutuldu; SQLAlchemy'ye taşınırken tablolara
  `tenant_id`, `belge_id` eklenecek (bugün tek belge varsayımı `belge LIMIT 1`)
- Frontend: vanilla JS → React'a taşınırken API sözleşmesi korunur (REST şemaları hazır)
- `extract.py` şemaları SaaS'ta kiracıya göre dinamikleşir (katalog enjeksiyonu zaten parametrik)
- Kayıt silme → iptal/ters kayıt modeline dönüşecek (denetim izi için)
- Kur servisi: TCMB EVDS API'sinden otomatik kur çekme (bugün elle)
