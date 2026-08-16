# DİİBPro — Yapılacaklar Listesi

> Bu dosya projenin canlı iş listesidir. Her geliştirme turunda güncellenir:
> yeni işler eklenir, bitenler ✅ işaretlenir. Sıralama = öncelik.

## 📌 Kullanıcı kararları (kapalı — tekrar açma)

- **Cloudflare olduğu gibi kalacak** (Flexible SSL). Subdomain üzerinde; diğer sistemleri etkilememek için dokunulmayacak. Origin'e https yönlendirmesi EKLENMEYECEK. (2026-08-17)
- **Admin parolası sistem tamamen bitene kadar `matek2026` kalacak.** Değiştirilmeyecek; parolalar asla sorulmadan değiştirilmez. (2026-08-17)

> Bilgi notu: İhracat kalem tutarları — kaynak Excel'de kalem fiyatı olmadığından fatura toplamı kg orantısıyla dağıtıldı (kayıt notlarında yazıyor); gerçek kalem fiyatları girilirse düzenleme ekranından güncellenebilir.

## 🟢 Yol haritası — SaaS fazı (docs/SAAS-MIMARI.md)

- [ ] E-posta bildirimleri: uyarı motorundaki kritik uyarılar e-posta ile de gitsin (SMTP bilgisi gerekli)
- [ ] DYS XML/Excel içe aktarım (sürükle-bırak)
- [ ] e-Fatura XML alımı
- [ ] PostgreSQL + Docker Compose geçişi (çok kiracılı ölçekleme)
- [ ] Gümrük müşaviri paneli (çok firma görünümü)
- [ ] Kapatma dilekçesi çıktısı (kapatma raporu setine resmî dilekçe şablonu eklenmesi)

## 🟡 Sırada — kapsam genişletme (opsiyonel)

- [ ] Toplu seçim + kolon genişliği, `dataTable()` bileşenini kullanmayan sayfalara da yayılabilir: Depo, Üretim, Kalite Kontrol, Muhasebe (cari/fatura/ödeme), Yönetim (çalışanlar) şu an düz `<table>` kullanıyor, sıralama/sürükle/genişlik/toplu seçim yok. İstenirse bu sayfalar da `buildKalemTable()`'a taşınabilir.

## ✅ Tamamlananlar

- [x] **İhracat Fatura Sarf Tablosu raporu** (`/api/rapor/sarf`) — Excel'deki İHR.FAT. SARF sayfasının sistemleştirilmiş karşılığı, 3 sayfalık set (Görüntüle/Excel/PDF):
  - *Fatura Sarf Dökümü*: 485 kalem satır satır — Sıra/Fatura/Tarih/Müşteri/Ülke/GTİP/DİİB Satır Kodu/Kalem No/Ürün Adı/**Alkol Tipi**/**Renk**/İhraç kg + 12 hammaddenin hesaplanmış sarf kg'ı + TOPLAM (293.840 kg, Excel ile birebir)
  - *Alkol Tipi Özeti*: mamul grubu bazında toplamlar + alkol tipi ara toplamları — **aynı renk farklı alkol ayrımı** burada net görünür (örn. BEYAZ: etil 008→127.590 kg, metil 011→1.720 kg, isopropil 003→280 kg; reçeteler tamamen farklı)
  - *Reçete Katsayı Matrisi*: Excel'in 13-160. kolonlarındaki katsayı bloğunun okunur hali (grup × hammadde)
  - Renk, DİİB satır kodu grubundan türetilir (001/005/009=SİYAH, 003/008/011=BEYAZ, 004/006/012=ŞEFFAF, 002/007/010=DİĞER); alkol tipi mamul kategorisinden. Canlıda 3 formatta doğrulandı (2026-08-17)
- [x] **Canlı Sarf Tablosu** — Raporlar sayfasına gömülü, İHR.FAT. SARF'ın açık/dinamik hali: sistemdeki güncel kayıtlardan anlık hesaplanır (kayıt ekle/sil/düzenle → tablo değişir). Arama + alkol tipi + renk + ülke filtreleri, KPI özet şeridi, 24 kolon (12 kimlik + 12 hammadde sarfı), sıralama/sütun düzeni/CSV/sayfalama, filtreye göre hammadde bazlı TOPLAM satırı. Veri ucu: `/api/rapor/sarf/veri` (rapor formatlarıyla aynı hesap çekirdeğini kullanır). Doğrulama: BEYAZ+Metil → yalnız titandioksit 774 kg + metil 946 kg; BEYAZ+Etil → tamamen farklı reçete seti (2026-08-17)
- [x] **Tüm tablolar için 4 iyileştirme** (`dataTable()` çekirdeğine eklendi — İthalat/İhracat/Evrak Arşivi/Canlı Sarf Tablosu'nun tamamında otomatik geçerli):
  1. **Toplu işlemler**: her satırda seçim kutusu + "tümünü seç"; seçim yapılınca üstte mavi araç çubuğu (🗑️ Seçilenleri Sil, ⬇ Seçilenleri CSV İndir). İthalat/İhracat'ta kalem bazlı toplu silme, Evrak Arşivi'nde belge bazlı toplu silme — her biri backend'e tek tek DELETE atıp sonucu (N başarılı / M başarısız) bildiriyor
  2. **Sütun sürükle-bırak artık sayfayı/tabloyu başa kaydırmıyor**: `rerenderTable()` şimdi tablo içi yatay kaydırmayı (`dt-wrap.scrollLeft`) ve sayfa dikey kaydırmasını render öncesi alıp render sonrası geri yüklüyor — gerçek sürükle-bırak olayıyla test edildi, kaydırma konumu birebir korundu
  3. **Kolon genişliği ayarlanabilir**: her başlığın sağ kenarında tutamaç (fare + dokunmatik); genişlik hesaba kayıtlı (`localStorage`), "Varsayılana dön" ile sıfırlanabilir
  4. **Sayfa yenileme (F5) artık her zaman Panel'e atmıyor**: `switchTab()` URL hash'ini günceller (`#ithalat`, `#muhasebe`...), yenilemede son bulunulan sekmeye dönülüyor; hash yoksa (ilk giriş) Panel varsayılan kalıyor. Canlıda gerçek F5 ile doğrulandı
  - Evrak Arşivi tablosu bu turda düz `<table>`'dan `dataTable()` bileşenine taşındı — artık o da sıralanabilir/sürüklenebilir/toplu seçilebilir (2026-08-18)

- [x] Excel analizi: DİİB-4 tüm sayfalar + DİİB klasörü belgeleri (2026-08-16)
- [x] Local MVP: FastAPI + SQLite, fotoğraf → çıkarım → stok/taahhüt akışı
- [x] Reçeteler + taahhüt listesi Excel'den otomatik tohum (18 grup, 15 mamul)
- [x] Pazar araştırması (rakip DİİB yazılımları) + SaaS mimari dokümanı
- [x] OCR motoru (Tesseract tur+eng, varsayılan, ücretsiz) — AI opsiyonel hale getirildi
- [x] Showcase sayfası + login sistemi (scrypt + oturum çerezi)
- [x] Masaüstü kenar menülü panel + mobil ayrı görünüm
- [x] Matek Kimya firma kaydı; Excel geçmişi aktarımı (7 ithalat, 39 ihracat, 484 kalem, 293.680 kg)
- [x] Filtreleme (arama, tarih aralığı, kaynak) — ithalat/ihracat listeleri
- [x] Profil sayfası (bilgi + parola değiştirme)
- [x] Yönetim: çalışan ekleme (rol: yönetici/operatör/izleyici), birim yönetimi
- [x] Fabrika modülleri: Muhasebe (cari/fatura/ödeme, otomatik backfill), Depo (stok+hareket), Üretim (iş emri → otomatik depo hareketleri), Kalite Kontrol (test kayıtları)
- [x] Panelde birim özet kartları
- [x] Sunucu dağıtımı: diibpro.cicibyte.com (systemd + nginx + SSL, Cloudflare)
- [x] Excel benzeri kalem tabloları: sıralama, sürükle-bırak sütun düzeni (kullanıcıya kayıtlı), göster/gizle, CSV, satır düzenle/sil/indir
- [x] Sol menü scroll düzeltmesi
- [x] GitHub reposu + profesyonel README (github.com/RealMrNovember/diibpro)
- [x] Kalem detayları: GTİP + gerçek kalem no (beyanname/fatura satır numarası) — DB, Excel aktarımı (484/484 dolu), API, OCR/AI şemaları, formlar, düzenleme kutusu; canlıda doğrulandı (2026-08-16)
- [x] Raporlar 3 format: Excel + PDF indirme + tarayıcıda görüntüleme (yazdırma dahil) (2026-08-16)
- [x] Profesyonel Evrak Arşivi: 36 geçmiş belge kategorili; kategori çipleri, tür filtresi, arama, yükleme/indirme/silme (2026-08-16)
- [x] Uyarı motoru (belge süresi, taahhüt açığı, izin aşımı, eksi stok, açık beyanname, vadesi geçmiş fatura) + TCMB kur servisi + muhasebede döviz ayrıştırması (2026-08-16)
- [x] Ürün ailesi ayrıştırması (Etil/Metil/İsopropil Alkollü, Laklar, Katkı, İncelticiler) + ihracat aile filtresi (2026-08-16)
- [x] Veri tamamlama: 485 kalem / 293.840 kg — Excel ile birebir; kalem tutarları kg orantısıyla dağıtıldı (2026-08-16)
- [x] Tam genişlik responsive düzen + deploy.sh (tek komut) + sunucuda günlük DB yedeği (cron 03:10, 30 gün) (2026-08-16)
- [x] Admin parolası eski haline alındı (matek2026) — parolalar bir daha asla sorulmadan değiştirilmeyecek (2026-08-16)
- [x] İthalat/İhracat sayfaları profesyonel kurgu: sayfa yatay kaymaz (kayma yalnızca tablo içinde), KPI özet şeridi (kalem/belge/KG/ülke/döviz bazlı tutar), sayfalama (25-250/Tümü, hesaba kayıtlı), filtreye göre TOPLAM satırı (sabit alt satır), mobil özet kartı, sürüm damgalı asset önbelleği — canlıda doğrulandı (2026-08-17)

- [x] Hammadde DİİB satır kodları belgeden teyit edildi: kaynak = DİİB-4 Excel **"İTH. ve SARF MİKTARLARI" (Ithal Esya Listesi)** sayfası. Sıralama (.001 PİGMENT → .009 POLİÜRETAN REÇİNE) sistemdekiyle birebir aynı çıktı; ek olarak her maddenin **DİİB ithal izin miktarı** (toplam 634.220 kg / 10.017.273 USD) hammadde kartlarına işlendi — izin aşımı uyarıları artık gerçek limitlerle çalışıyor. Çapraz doğrulama: sistemdeki 85.790 kg ithalat, belgedeki gerçekleşen miktarlarla birebir (2026-08-17)
- [x] **Genel tasarım/düzen taraması** — masaüstü (1366×768, 1440×768, 1600×900) ve mobil (375×812) her sayfa tek tek gezildi, bulunanlar düzeltildi:
  - Kenar menü artık hiçbir ekran yüksekliğinde yarıda kesilmiyor: logo ve kullanıcı/çıkış bloğu her zaman sabit, yalnızca orta nav listesi (çok kısa ekranlarda) kendi içinde kayar; buton boyutları kompaktlaştırıldı (13 menü öğesi + 3 bölüm başlığı artık 900px'te 135px pay bırakarak sığıyor)
  - **Kritik mobil hata**: `.two-col` grid düzeni 7 sayfada (Panel, Yönetim, Depo, Üretim, Kalite, Muhasebe, Evrak Arşivi) grid çocuğuna `min-width:0` eksikliği yüzünden geniş tabloları ekranın dışına taşırıyordu — önceki tur eklenen `overflow-x:hidden` ile bu içerik mobilde tamamen erişilemez hale gelmişti. Tek satırlık CSS düzeltmesiyle tüm sayfalarda tablo kayması artık kendi kutusunda, sayfa sabit
  - Parola sıfırlama (Yönetim) ve tahsilat/ödeme tutarı girişi (Muhasebe) native `prompt()`'tan uygulamanın kendi modal/form tasarımına taşındı — tutarlılık ve profesyonellik için
  - **Ürün adlarında Türkçe karakter bozukluğu** (15 mamul: "BAZLi", "DIGER", "SEFFAF", "iSTAMPA" vb.) düzeltildi — kaynak: "AKKİM DİİB FATURADA KULLANILACAK ÜRÜN TANIMLARI.docx" resmî fatura açıklaması esas alındı (doğru yazım: MÜREKKEBİ, BAZLI, SİYAH, DİĞER...); mevcut veritabanları migration ile otomatik düzeltildi, kategori ataması bozulmadı
  - "Metil Alkollü (Istampa)" → "Metil Alkollü (İstampa)" (dotless→dotted İ) düzeltildi
  - Landing, login sayfaları ve tüm sekmeler: yatay taşma yok, kırık görsel yok, undefined/NaN/[object Object] sızıntısı yok, eski "Akkim" marka izi yok

> Not: Frontend değişikliklerinde `frontend/index.html` içindeki `?v=YYYYMMDDx` sürüm damgası artırılmalı (CDN önbelleği).
> Not: Belge listesi kaynağı — DİİB klasörüne eklenen "DİİB TEŞVİK KULLANIM HESAPLAMA LİSTESİ" klasörü 2021-2022 belgelerinin (21.2.06327 / 22.2.06906) çalışma dosyalarını içerir; aktif belgenin (2024/D1-03798) ithal eşya listesi ana Excel'in "İTH. ve SARF MİKTARLARI" sayfasındadır.
