# Türkiye DİİB/DİR Takip Yazılımları — Pazar Araştırması (Tam Rapor)

> 16.08.2026 tarihli web araştırması. Yalnızca doğrulanabilen bilgiler; doğrulanamayanlar
> "bulunamadı" olarak işaretlendi. Türk B2B yazılım pazarında fiyatlar genelde kamuya açık
> değil — neredeyse tüm oyuncular "teklif al" modeliyle çalışıyor.

## 1. Rakip Tablosu

| Firma | Ürün | Ana Özellikler (doğrulanan) | Dağıtım Modeli | Fiyat | Web |
|---|---|---|---|---|---|
| **Evrim Yazılım** (pazar lideri, 1992'den beri) | DİİB Modülü (Veri Birleştirme Platformu / VRB içinde) | DYS belge XML'i + sarfiyat Excel'i yükleyerek otomatik taahhüt takibi; müşavir beyannamelerinin "akıllı servislerle" anlık aktarımı (müşavir Evrim kullanmasa bile); ihracatta sarfiyata göre en uygun ithalat dosyasının otomatik seçimi ve düşüm; tescil öncesi otomatik TEV hesaplama + TARIC oranlarına göre optimizasyon; sektöre özel ikincil birim sarfiyatları | Bulut/platform (kurumsal ağırlıklı) | Açıklanmıyor (teklif usulü; İGMD ile ücretler konusunda yazışma olacak kadar tartışmalı) | evrim.com/dahilde-islem-izin-belgesi |
| **Evrim Yazılım** | Web Gümrük | Müşavir müşterileri için web ekranı: beyanname takibi, dahilde işleme takibi, antrepo stok, vergi hesaplama, finans/grafik raporlar | Web SaaS | Açıklanmıyor | webgumruk.com |
| **Mavi Bilişim** | Mavi Gümrük (Silver/Gold/Platin/Kurumsal) | "Düşümlü Belge Takip" modülü: dahilde/hariçte işleme, geçici ithalat/ihracat, TPS belgeleri; beyannameye entegre düşüm; **tescil öncesi aşım kontrolü**; GTİP/eşya tanımı/menşe uyum kontrolü; BİLGE/EDI entegrasyonu; TEV kapsamda; e-fatura ayrı ürün; web portal (Hizmet Online) | On-prem + bulut seçenekleri; Silver bulut tabanlı yıllık kullanım lisansı, eş zamanlı oturum sayısına göre esnek lisans | Rakam açıklanmıyor | mavibilisim.com.tr |
| **Bilgin Bilişim (Bilgin Yazılım)** | Detaylı Beyan vb. | Beyanname (BİLGE EDI/TCGB), özet beyan, e-fatura, e-arşiv, UBL okuma, Tareks XML; tüm rejim kodları | On-prem görünümlü (MySQL) | Açıklanmıyor | bilginyazilim.com.tr — DİİB'e özel modül detayı bulunamadı |
| **ATEZ Yazılım** | Customs Shield, AGSW, Customs X-ray | Yapay zekâ destekli beyanname hazırlama/kontrol; tescil öncesi hata tespiti; beyanname risk kontrolü; teminat yönetimi | Kurumsal platform/SaaS | Açıklanmıyor | atez.com — DİİB taahhüt kapatmaya özel modül doğrulanamadı |
| **Sighthem** | Sighthem (dış ticaret SaaS) | DİİB operasyonel takibi: ithal hammadde, ürün reçetesi, sarfiyat, kalan taahhüt/süre uyarıları; CRM, kartvizit OCR, AI çeviri/özet; "kurulum saatler içinde, şeffaf fiyat" iddiası | Hazır SaaS (modern, web) | "Şeffaf fiyat" iddiası; rakam doğrulanamadı | sighthem.com |
| **Logo Netsis** | Netsis ERP dış ticaret | DİİB takibi ERP içinde; muhasebe/e-defter ağırlıklı | On-prem ERP + bayi | Bayi üzerinden lisans | logo.com.tr |
| **DİA Yazılım** | DİA Dış Ticaret | İthalat/ihracat operasyon kartları, maliyet dağıtımı, bulut ERP | Bulut SaaS | Modül bazlı abonelik | dia.com.tr — DİİB'e özel taahhüt/sarf modülü bulunamadı |
| **DBI Yazılım (Monovi)** | Exwiz | İhracat belgeleri, proforma, çeki listesi, konteyner simülasyonu | SaaS/web | Açıklanmıyor | dbisoft.com — DİİB taahhüt takibi bulunamadı |
| **GOOSOFT** | Dış Ticaret Yazılımı | İthalat-ihracat kartları, maliyet dağıtımı, KDV iade dekontu, muhasebe entegrasyonu | Bulut | Açıklanmıyor | goosoft.com.tr — DİİB/sarf-reçete bulunamadı |
| **ÜNSPED (UGM)** | Müşteri Çalışma Portalı (MÇP) | Beyanname verileri, antrepo stok, süreç takibi; DİİB/HİİB takibi uzman ekip hizmeti olarak | Müşavirlik hizmetine bağlı portal | Hizmet sözleşmesine dahil | ugm.com.tr |
| **Doğruer** | — | Bağımsız satılan DİİB yazılımı bulunamadı | — | — | dogruer.com |

**Bulunamayanlar:** NetBT, Bilgeport (BİLGE devletin sistemi, ticari ürün değil), "Trade Vision"
(yalnız danışmanlık firmaları), SoftTrade (muhtemel kasıt SOFT — softtrans; DİİB modülü doğrulanamadı).

**Pazarın yapısı:** İki katman: (1) gümrük müşavirliği yazılımları (Evrim, Mavi, Bilgin) —
DİİB'i müşavir perspektifinden, beyanname-düşüm odaklı çözer; (2) ERP/dış ticaret modülleri
(Logo Netsis, DİA, SOFT). Sanayici DİİB sahibine odaklı bağımsız modern SaaS olarak tek görünür
oyuncu Sighthem; onun da DİİB derinliği (TEV, kapatma, DYS) belirsiz.

## 2. Sektör Standardı Özellik Seti

1. Belge taahhüt takibi: satır bazında miktar-değer düşümü, kalan taahhüt, döviz kullanım oranı
2. Süre yönetimi: belge süresi, ek süre, uyarı/alarm
3. Sarf/reçete hesaplama: reçete → ihracattan hammadde düşümü; fire; ikincil işlem görmüş ürün
4. Beyanname entegrasyonu: BİLGE/EDI; müşavirden anlık veri akışı (Evrim'in kozu); tescil öncesi aşım kontrolü (Mavi)
5. DYS entegrasyonu: 19.09.2022'den beri tüm DİR işlemleri yalnızca DYS'de; yazılımlar XML/Excel
   indir-yükle ile entegre; canlı API sunan ürün bulunamadı
6. TEV hesaplama (tescil öncesi hesap; Evrim müşavire otomatik TEV servisi sunuyor)
7. Kapatma dosyası hazırlama (YMM tespit raporuna altlık)
8. Raporlama: gerçekleşme, taahhüt açığı, belge kapsamı stok
9. KDV istisnası / tecil-terkin listeleri (pazarda zayıf — kısmi boşluk)
10. e-Fatura entegrasyonu (müşavir yazılımlarında var; DİİB bağlamı zayıf)

## 3. Pazar Boşluğu ve Farklılaşma

**a) OCR / fotoğraftan belge okuma + otomatik sarf: doğrudan rakip yok.** AI belge okuma başka
segmentlerde var (ATEZ — müşavir beyanname kontrolü; Digiform — belge işleme; Narin Gümrük —
kendi iç süreci; Sighthem — yalnız kartvizit OCR). "Fotoğraf yükle → satırlar ayrışsın →
reçeteyle sarf otomatik" akışını sunan ürün bulunamadı.

**b) Sanayici odaklı self-servis SaaS boşluğu.** Belge sahibi KOBİ'nin kurulumsuz, mobil,
şeffaf fiyatlı ürünü pratikte yok.

**c) Şeffaf abonelik fiyatı.** Pazarın tamamı "teklif al"; Evrim'in ücretleri İGMD yazışmasına
konu. Açık fiyat sayfası farklılaştırıcı.

**d) DYS dosya entegrasyonunu otomatikleştirme.** Sürükle-bırak XML/Excel, otomatik eşleştirme,
tek tık kapatma dosyası.

**e) Dikeyleşme.** Kimya/mürekkep gibi reçetesi karmaşık sektörlere özel sarf mantığı.

**Riskler:** Evrim'in müşavir ağı şebeke etkisi (karşı hamle: OCR kanalı + DYS dosya alımı);
TEV/kapatma mevzuat derinliği (hesaplar "müşavir onayına hazır taslak" olarak konumlanmalı).

## 4. Kaynaklar

- https://evrim.com/dahilde-islem-izin-belgesi/ · https://webgumruk.com/
- https://mavibilisim.com.tr/mavi-gumruk-kurumsal.html · https://www.mavibilisim.com.tr/mavi-gumruk-silver.html
- https://bilginyazilim.com.tr/_tr/urunlerimiz/detayli-beyan/
- https://sighthem.com/tr/karsilastirma/en-iyi-dis-ticaret-yazilimi
- https://ugm.com.tr/makaleler/neden-unsped-gumruk-ve-lojistik-hizmetleri/
- https://btplatform.net/ (ATEZ)
- https://www.dia.com.tr/cozum/dis-ticaret-yazilimi/ · https://goosoft.com.tr/dis-ticaret/ · https://dbisoft.com/
- DYS geçişi: https://ticaret.gov.tr/destekler/destek-yonetim-sistemi-dys · https://dys.ticaret.gov.tr/
- OCR ekosistemi: https://www.digiform.com.tr/ · https://naringumruk.com/yapay-zeka-destekli-beyanname-yaziminda-yeni-donem-a-new-era-in-ai-powered-customs-declaration-preparation/
- Evrim ücretleri hk. İGMD: https://www.igmd.org.tr/gumruk-musavir-firmalarina-yazilim-program-ucretleri-hakkinda7022024-165355_haberi
