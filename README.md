# Keenetic Zapret Lite Panel (KZLP)

Keenetic router + [Entware](https://github.com/Entware/Entware) + [bol-van/zapret](https://github.com/bol-van/zapret) (klasik **nfqws**) için hafif, **Türkçe** web yönetim paneli.

Panel, Zapret’i başlat/durdur, Keenetic **Zapret bağlantı politikasına** bağlı cihazları listele, domain listelerini düzenle, yedek al ve GitHub’dan nfqws güncellemesini kontrol etmenizi sağlar.

> **Not:** Başka Zapret web panelleri (KZM2, nfqws-web vb.) ile aynı anda kullanmayın (NFQUEUE çakışması). Bu proje **klasik zapret v72.x** ve kuyruk **200** için tasarlanmıştır.

## Ne işe yarar?

| Özellik | Açıklama |
|--------|----------|
| **Politika modu** | Bypass yalnızca Keenetic’te *Zapret* bağlantı kuralına atanmış cihazlara uygulanır (`FILTER_MARK=0xffffaaa`). |
| **Durum** | nfqws çalışıyor mu, kurulu sürüm, WAN arayüzü. |
| **Cihaz listesi** | Politikadaki MAC, IP ve Keenetic’teki **cihaz adı** (ör. `PC YA Mac Mini`). |
| **Siteler** | Öğrenilen (DPI engeli), istisna ve hedef domain listeleri. |
| **Yedek** | Zapret config + hostlist + panel ayarlarını `.tar.gz` olarak saklar. |
| **Güncelleme** | Zapret: [bol-van/zapret](https://github.com/bol-van/zapret) `nfqws` ikilisi. KZLP: [bu repo](https://github.com/yetkina/keenetic-zapret-lite-panel) panel dosyaları (otomatik). |

Panel **tüm internet geçmişini** kaydetmez. *Öğrenilen* liste, politikalı cihazlarda DPI engeli tespit edilen domainleri otomatik yazar.

## Gereksinimler

- Keenetic (NDMS 3.x / 4.x), **Entware** USB’de (`/opt`)
- Kurulu **klasik zapret** (`/opt/zapret`, `nfqws`, `S90-zapret`)
- Keenetic’te bağlantı kuralı: **Zapret** (cihazları bu kurala ekleyin)
- `lighttpd`, `curl`, `iptables`, `ipset` (Entware paketleri)
- LAN’dan erişim: `http://<router-ip>:8088/`

## Kurulum

### 1) Dosyaları router’a kopyalayın

Mac veya PC’den (SSH portu genelde Entware **222**):

```bash
git clone https://github.com/yetkina/keenetic-zapret-lite-panel.git
cd keenetic-zapret-lite-panel
scp -P 222 -r www etc scripts root@192.168.53.1:/opt/tmp/kzlp-src/
```

### 2) Deploy script

Router’da:

```bash
ssh -p 222 root@192.168.53.1
cd /opt/tmp/kzlp-src
sh scripts/deploy.sh
```

Script: klasik zapret’i politika moduna alır, `lighttpd`’yi 8088’de açar, panel dosyalarını `/opt/www/kzlp` altına yerleştirir.

### 3) Panel adresi

Tarayıcıda: `http://192.168.53.1:8088/`  
(Router LAN IP’nizi kullanın.)

## Kullanım

### Sol menü

| Menü | Açıklama |
|------|----------|
| **Panel** | Durum, politika cihazları, siteler, yedek, güncelleme |
| **Zapret Kurulum** | Zapret yoksa otomatik açılır; model + ISS seçerek kurulum |

Panel açıldığında **Zapret kurulu mu** kontrol edilir. Kurulu değilse **Zapret Kurulum** sayfasına yönlendirilirsiniz.

### Zapret Kurulum sihirbazı

1. **Model** — `ndmc show version` ile otomatik (ör. Keenetic Hero KN-1012)
2. **ISS** — PPPoE kimliğinden tahmin (`@kablonet`, `@ttnet` …) veya listeden seçim
3. **Kur** — GitHub’dan [bol-van/zapret](https://github.com/bol-van/zapret) indirilir, ISS profiline göre `NFQWS_OPT` ayarlanır, politika modu (`FILTER_MARK=0xffffaaa`) etkinleştirilir

Desteklenen ISS profilleri (klasik nfqws): Kablonet, Kablonet Fiber, Turk Telekom, Superonline, TurkNet, Vodafone, Genel.

### Zapret politikası — cihazlar

- Keenetic web arayüzü → **Bağlantı kuralı** → **Zapret** → cihaz ekleyin/çıkarın.
- Panel bu kuraldaki cihazları otomatik listeler; yeni cihaz için router arayüzünü kullanın (panelden MAC eklenmez).

### Durum

- **Başlat / Durdur / Yeniden başlat** — `S90-zapret` üzerinden nfqws ve firewall kuralları.

### Siteler / domainler

| Sekme | Dosya | Anlamı |
|-------|--------|--------|
| **Öğrenilen** | `zapret-hosts-auto.txt` | Otomatik (DPI engeli tespiti). |
| **İstisna** | `zapret-hosts-user-exclude.txt` | Bypass uygulanmaz (banka, e-Devlet vb.). |
| **Hedef** | `zapret-hosts-user.txt` | Elle eklenen hedef domainler. |

Domain eklerken sadece ana alan adı yazın (ör. `discord.com`). Değişiklikten sonra firewall kuralları yenilenir.

### Yedekle / Geri yükle

Yedekler: `/opt/etc/kzlp/backups/kzlp_*.tar.gz`  
Config, hostlist dosyaları ve panel ayarlarını içerir.

### Güncelleme

**Zapret (nfqws)** — **Sürüm kontrol** → [bol-van/zapret](https://github.com/bol-van/zapret) son etiketi. **Güncelle** → yalnızca `nfqws` ikilisi; kısa kesinti olabilir.

**KZLP panel** — **Zapret** menüsünde *KZLP Panel sürümü*:

- Kurulu sürüm: `/opt/etc/kzlp/kzlp.version`
- Değişiklik notları: `/opt/etc/kzlp/CHANGELOG.md` (panelde gösterilir)
- Açılışta GitHub ile otomatik karşılaştırma; yeni sürüm varsa **Paneli güncelle** etkinleşir
- Güncelleme: GitHub **release** etiketi (ör. `v1.1.0`) veya `main` arşivi; `scripts/kzlp-self-update.sh`

Sürüm dosyaları (repo kökü):

| Dosya | Açıklama |
|-------|----------|
| `VERSION` | Yayınlanan panel sürümü |
| `CHANGELOG.md` | Her sürümde Eklendi / Düzeltildi / Değiştirildi |
| `etc/kzlp/kzlp.version` | Şablon (kurulumda `/opt/etc/kzlp/kzlp.version` olur) |

Yeni panel sürümü yayınlamak: `VERSION` ve `CHANGELOG.md` güncelleyin → commit → GitHub’da `vX.Y.Z` release oluşturun.

## Zapret config (politika modu)

Deploy script şunu ekler / korur:

```bash
FILTER_MARK=0xffffaaa
IFACE_WAN=ppp0   # Kablonet / PPPoE örneği
```

Tüm ağa bypass vermek için `FILTER_MARK` satırını config’ten kaldırıp zapret’i yeniden başlatın (önerilmez; politika dışı cihazlar da bypass alır).

## Sorun giderme

| Belirti | Kontrol |
|--------|---------|
| Panel 403 / boş | `lighttpd -f /opt/etc/lighttpd/lighttpd.conf` çalışıyor mu? Port **8088** |
| Discord/Roblox açılmıyor | Cihaz **Zapret** politikasında mı? `pgrep -a nfqws` |
| Ad sütunu boş | `/tmp/ndnproxyhostmap.conf` router’da var mı (Keenetic cihaz kaydı) |
| Çift NFQUEUE | Başka Zapret paneli / nfqws2 süreci kapalı mı? |

API testi (router içinden):

```bash
curl -s "http://127.0.0.1:8088/api.cgi?action=status"
```

## Proje yapısı

```
www/kzlp/                    # index.html + api.cgi
etc/kzlp/                    # settings.json, kzlp.version
etc/lighttpd/                # kzlp.conf (port 8088)
scripts/deploy.sh            # kurulum
scripts/kzlp-self-update.sh  # panel GitHub guncellemesi
scripts/changelog-parse.sh   # CHANGELOG -> JSON
VERSION                      # panel surumu
CHANGELOG.md                 # degisiklik gunlugu
```

## Lisans ve teşekkür

- Panel kodu: MIT — bkz. [LICENSE](LICENSE)
- [bol-van/zapret](https://github.com/bol-van/zapret) — ayrı lisansına tabidir
- Keenetic / Entware — ticari markalar ilgili sahiplerine aittir

## Cursor / yapay zeka ile GitHub

Mac’te `gh auth login` ile giriş yaptıysanız, Cursor agent `gh repo create` ve `git push` yapabilir. **Token veya şifreyi sohbete yapıştırmayın.** Gerekirse yalnızca boş repo oluşturup push’u siz yapın:

```bash
gh repo create keenetic-zapret-lite-panel --public --source=. --remote=origin --push
```
