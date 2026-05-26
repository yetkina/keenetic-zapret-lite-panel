#!/bin/sh
# KZLP panel — GitHub uzerinden kendi kendini gunceller
set -e

export PATH="/opt/sbin:/opt/bin:/opt/usr/sbin:/opt/usr/bin:/sbin:/bin"

KZLP_DIR="/opt/etc/kzlp"
LOG="/opt/tmp/kzlp_panel_update.log"
STATUS="/opt/tmp/kzlp_panel_update.status"
REPO="${KZLP_GITHUB_REPO:-yetkina/keenetic-zapret-lite-panel}"
TAG="${1:-}"

log() {
  echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"
}

set_status() {
  printf '%s' "$1" > "$STATUS"
}

norm_ver() {
  echo "$1" | sed 's/^[vV]//;s/[^0-9.].*//'
}

rm -f /opt/tmp/kzlp_panel_update.done
: > "$LOG"
set_status "running"

log "KZLP panel guncellemesi basladi"

if ! command -v curl >/dev/null 2>&1; then
  log "HATA: curl yok"
  set_status "error"
  exit 1
fi

if [ -z "$TAG" ]; then
  raw=$(curl -fsSL -m 30 -H "User-Agent: KZLP-Update" \
    "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null) || true
  TAG=$(echo "$raw" | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -1)
  [ -z "$TAG" ] && TAG=$(curl -fsSL -m 15 "https://raw.githubusercontent.com/$REPO/main/VERSION" 2>/dev/null | tr -d '\r\n ')
  [ -z "$TAG" ] && TAG="main"
fi

log "Hedef surum: $TAG"

tmp="/opt/tmp/kzlp_pup_$$"
mkdir -p "$tmp"

case "$TAG" in
  main|master)
    url="https://github.com/$REPO/archive/refs/heads/main.tar.gz"
    ;;
  *)
    url="https://github.com/$REPO/archive/refs/tags/${TAG}.tar.gz"
    ;;
esac

log "Indiriliyor: $url"
curl -fsSL -o "$tmp/src.tgz" "$url" || {
  log "HATA: Indirme basarisiz"
  set_status "error"
  exit 1
}

tar -xzf "$tmp/src.tgz" -C "$tmp" || {
  log "HATA: Arsiv acilamadi"
  set_status "error"
  exit 1
}

srcdir=$(ls -1 "$tmp" | head -1)
root="$tmp/$srcdir"
[ -d "$root" ] || { log "HATA: Kaynak dizin yok"; set_status "error"; exit 1; }

mkdir -p /opt/www/kzlp "$KZLP_DIR" /opt/etc/lighttpd

log "Panel dosyalari kopyalaniyor..."
cp -f "$root/www/kzlp/"* /opt/www/kzlp/
chmod +x /opt/www/kzlp/api.cgi 2>/dev/null

for f in requirements.sh isp-profiles.sh zapret-install.sh kzlp-self-update.sh; do
  [ -f "$root/scripts/$f" ] && cp -f "$root/scripts/$f" "$KZLP_DIR/" && chmod +x "$KZLP_DIR/$f" 2>/dev/null
done

[ -f "$root/etc/kzlp/settings.json" ] && cp -f "$root/etc/kzlp/settings.json" "$KZLP_DIR/"
[ -f "$root/etc/lighttpd/kzlp.conf" ] && cp -f "$root/etc/lighttpd/kzlp.conf" /opt/etc/lighttpd/
[ -f "$root/CHANGELOG.md" ] && cp -f "$root/CHANGELOG.md" "$KZLP_DIR/"
[ -f "$root/VERSION" ] && cp -f "$root/VERSION" "$KZLP_DIR/kzlp.version"

_newv=$(norm_ver "$(cat "$KZLP_DIR/kzlp.version" 2>/dev/null)")
log "Yeni KZLP surumu: $_newv"

/opt/etc/init.d/S80lighttpd restart >/dev/null 2>&1 || killall lighttpd 2>/dev/null; lighttpd -f /opt/etc/lighttpd/lighttpd.conf 2>/dev/null || true

rm -rf "$tmp"
set_status "done"
touch /opt/tmp/kzlp_panel_update.done
log "Panel guncellemesi tamam ($_newv)"
exit 0
