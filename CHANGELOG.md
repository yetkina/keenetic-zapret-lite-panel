# KZLP Değişiklik Günlüğü

Tüm önemli değişiklikler [Semantic Versioning](https://semver.org/) ile sürümlenir.

## [1.1.2] - 2026-05-26

### Düzeltildi
- Router modeli: `ndmc` çıktısında `tr -d K` Keenetic adını bozuyordu; Hero (N-1012) vb. artık doğru tespit edilir
- `/proc/device-tree/model` yalnızca `KN-1012` döndüğünde Hero adına eşlenir

### Değiştirildi
- **Panel (Canlı):** KZLP sürümü üst çubukta, menüde ve sistem özetinde gösterilir

## [1.1.1] - 2026-05-26

### Düzeltildi
- GitHub sürüm karşılaştırmasında güncelleme mevcut bayrağı (`update_available`) yanlış `false` dönüyordu

## [1.1.0] - 2026-05-26

### Eklendi
- KZLP panel sürümü (`VERSION`, `CHANGELOG.md`) ve kurulu sürüm dosyası (`kzlp.version`)
- Zapret menüsünde **KZLP Panel sürümü**: değişiklik notları, GitHub güncelleme kontrolü
- Tek tıkla panel güncellemesi (`kzlp-self-update.sh`, GitHub release veya `main` arşivi)
- Canlı panelde KZLP sürümü gösterimi; açılışta otomatik güncelleme kontrolü

### Değiştirildi
- Zapret kurulu sürümü `zapret.version` dosyasında tutulur (eski `installed.version` taşınır)

## [1.0.0] - 2026-05-26

### Eklendi
- Türkçe web paneli (KZLP) — lighttpd port 8088
- **Panel (Canlı):** CPU, RAM, disk, sıcaklık, Zapret durumu, ISS ve sistem özeti
- **Zapret** menüsü: politika cihazları (Keenetic adları), siteler (öğrenilen / istisna / hedef), yedekleme
- **Zapret Kurulum** sihirbazı: model ve ISS otomatik tespiti, ISS profilleri (Kablonet, Turk Telekom, Superonline…)
- Keenetic OPKG gereksinim kontrolü (yeşil onay işaretleri)
- Klasik bol-van zapret (nfqws) kurulumu ve politika modu (`FILTER_MARK=0xffffaaa`)
- Zapret nfqws GitHub güncellemesi (panelden)
- Otomatik hostlist öğrenme (`zapret-hosts-auto.txt`)

### Düzeltildi
- WAN arayüzü tespiti (`ppp0` / default route)
- Keenetic cihaz adları (`ndnproxyhostmap.conf`, base64 çözümü)
- Eski KZM2 / nfqws2 panelleri kurulumda otomatik kaldırma

### Notlar
- Zapret2 ile birlikte çalıştırılmamalıdır (NFQUEUE çakışması)
- Discord / Roblox için test edilmiş profil: Kablonet (`fake` + `ttl=2`)
