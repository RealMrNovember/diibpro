# DİİBPro — Yapılacaklar Listesi

> Bu dosya projenin canlı iş listesidir. Her geliştirme turunda güncellenir:
> yeni işler eklenir, bitenler ✅ işaretlenir. Sıralama = öncelik.

## 🟡 Sırada — kullanıcı teyidi / kararı bekleyenler

- [ ] Hammadde DİİB satır kodları teyidi: PİGMENT=.001 belgeden teyitli; .002-.009 önceki belgenin resmî sırasına göre atandı — **belgeden kontrol edilip yanlışsa Tanımlar'dan düzeltilmeli**
- [ ] Admin parolası: **kullanıcı kendisi değiştirecek** (Profil → Parola Değiştir). Parolalar asla sorulmadan değiştirilmez.
- [ ] Cloudflare SSL modu Full'e alınırsa origin https yönlendirmesini geri ekle
- [ ] İhracat kalem tutarları not: kaynak Excel'de kalem fiyatı olmadığından fatura toplamı kg orantısıyla dağıtıldı (kayıt notlarında yazıyor) — gerçek kalem fiyatları girilirse düzenleme ekranından güncellenebilir

## 🟢 Yol haritası — SaaS fazı (docs/SAAS-MIMARI.md)

- [ ] KDV istisna listesi raporu (maliye formatı — Excel'deki "KDV açısından maliye listesi" karşılığı)
- [ ] TEV tablosu (EK-8) raporu — ihracat×ithalat eşleştirme, %6,5 hesap
- [ ] Kapatma dosyası seti (taahhüt hesabı + kapanış dilekçesi çıktıları)
- [ ] Uyarı motoru: belge süresi, taahhüt açığı, izin aşımı, eksi stok (+ e-posta)
- [ ] TCMB EVDS kur servisi (kur alanı otomatik dolsun)
- [ ] DYS XML/Excel içe aktarım (sürükle-bırak)
- [ ] Muhasebede döviz ayrıştırması (USD/EUR bakiyeleri ayrı; şu an tek havuz)
- [ ] Deploy script (tek komut: paketle → yükle → restart)
- [ ] Günlük veritabanı yedeği (cron, sunucuda)
- [ ] PostgreSQL + Docker Compose geçişi (çok kiracılı ölçekleme)
- [ ] Gümrük müşaviri paneli (çok firma görünümü)
- [ ] e-Fatura XML alımı

## ✅ Tamamlananlar

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

> Not: Frontend değişikliklerinde `frontend/index.html` içindeki `?v=YYYYMMDDx` sürüm damgası artırılmalı (CDN önbelleği).
