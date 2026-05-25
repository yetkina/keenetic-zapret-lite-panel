#!/bin/sh
# KZLP — bol-van zapret (klasik nfqws) kurulumu
set -e

export PATH="/opt/sbin:/opt/bin:/opt/usr/sbin:/opt/usr/bin:/sbin:/bin"

ISP_ID="${1:-generic}"
LOG="/opt/tmp/kzlp_install.log"
STATUS="/opt/tmp/kzlp_install.status"
DONE="/opt/tmp/kzlp_install.done"
ZAPRET="/opt/zapret"
KZLP_DIR="/opt/etc/kzlp"
VERSION_FILE="$KZLP_DIR/installed.version"
GITHUB_REPO="bol-van/zapret"

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
if [ -f /opt/etc/kzlp/isp-profiles.sh ]; then
  . /opt/etc/kzlp/isp-profiles.sh
else
  . "$SCRIPT_DIR/isp-profiles.sh"
fi

log() {
  echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"
}

set_status() {
  printf '%s' "$1" > "$STATUS"
}

rm -f "$DONE"
: > "$LOG"
set_status "running"

valid_isp_id "$ISP_ID" || ISP_ID="generic"

log "KZLP Zapret kurulumu basladi (ISS: $(kzlp_isp_label "$ISP_ID"))"

# Entware
if [ ! -d /opt/bin ]; then
  log "HATA: Entware (/opt) bulunamadi"
  set_status "error"
  exit 1
fi

# Bagimliliklar (sessiz)
for pkg in curl ca-certificates iptables ipset; do
  opkg list-installed 2>/dev/null | grep -q "^$pkg " || opkg install "$pkg" >/dev/null 2>&1 || true
done

# Zapret arsivi indir
log "Zapret surumu kontrol ediliyor..."
raw=$(curl -fsSL -m 60 -H "User-Agent: KZLP-Install" "https://api.github.com/repos/$GITHUB_REPO/releases/latest") \
  || { log "HATA: GitHub erisilemedi"; set_status "error"; exit 1; }
tag=$(echo "$raw" | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -1)
url=$(echo "$raw" | tr ',' '\n' | sed -n 's/.*"browser_download_url": *"\([^"]*\)".*/\1/p' | grep '\.tar\.gz' | grep -vE 'openwrt|mips|x86|lexra' | head -1)
[ -n "$url" ] || { log "HATA: Arsiv URL bulunamadi"; set_status "error"; exit 1; }

tmp="/opt/tmp/kzlp_inst_$$"
mkdir -p "$tmp"
log "Indiriliyor: $tag"
curl -fsSL -o "$tmp/z.tgz" "$url" || { log "HATA: Indirme basarisiz"; set_status "error"; exit 1; }
tar -xzf "$tmp/z.tgz" -C "$tmp" || { log "HATA: Arsiv acilamadi"; set_status "error"; exit 1; }
srcdir=$(ls -1 "$tmp" | head -1)

if [ ! -d "$ZAPRET" ]; then
  log "Zapret dizini olusturuluyor: $ZAPRET"
  cp -a "$tmp/$srcdir" "$ZAPRET"
else
  log "Mevcut $ZAPRET — ikililer guncelleniyor"
  cp -a "$tmp/$srcdir/nfq" "$ZAPRET/" 2>/dev/null || true
  cp -a "$tmp/$srcdir/tpws" "$ZAPRET/" 2>/dev/null || true
  cp -a "$tmp/$srcdir/binaries" "$ZAPRET/" 2>/dev/null || true
  cp -a "$tmp/$srcdir/common" "$ZAPRET/" 2>/dev/null || true
  cp -a "$tmp/$srcdir/init.d" "$ZAPRET/" 2>/dev/null || true
  cp -a "$tmp/$srcdir/ipset" "$ZAPRET/" 2>/dev/null || true
  cp -a "$tmp/$srcdir/files" "$ZAPRET/" 2>/dev/null || true
fi
rm -rf "$tmp"

# Platform ikilileri
if [ -x "$ZAPRET/install_bin.sh" ]; then
  log "install_bin.sh calistiriliyor..."
  (cd "$ZAPRET" && ZAPRET_BASE="$ZAPRET" ./install_bin.sh) >>"$LOG" 2>&1 || log "UYARI: install_bin kismi hata (devam)"
fi

[ -x "$ZAPRET/nfq/nfqws" ] || { log "HATA: nfqws bulunamadi"; set_status "error"; exit 1; }

# Config
if [ ! -f "$ZAPRET/config" ]; then
  cp -f "$ZAPRET/config.default" "$ZAPRET/config" 2>/dev/null || true
fi
touch "$ZAPRET/config"

# WAN tespiti
wan=$(ip -4 route show default 2>/dev/null | awk '$1=="default" && $2=="dev" {print $3; exit}')
hint=$(kzlp_isp_wan_hint "$ISP_ID")
[ -z "$wan" ] && wan="${hint:-ppp0}"
[ -n "$hint" ] && { ip link show "$hint" >/dev/null 2>&1 && wan="$hint"; }
log "WAN arayuzu: $wan"

# NFQWS_OPT uygula
_nfqtmp="/opt/tmp/kzlp_nfqws_block.$$"
{
  echo 'NFQWS_OPT="'
  kzlp_isp_nfqws_opt "$ISP_ID"
  echo '"'
} > "$_nfqtmp"
_replaced=0
while IFS= read -r _line; do
  case "$_line" in
    NFQWS_OPT=*)
      [ "$_replaced" -eq 0 ] && cat "$_nfqtmp"
      _replaced=1
      _skip=1
      continue
      ;;
  esac
  [ "$_skip" -eq 1 ] && { [ "$_line" = '"' ] && _skip=0; continue; }
  printf '%s\n' "$_line"
done < "$ZAPRET/config" > "$ZAPRET/config.new"
[ "$_replaced" -eq 0 ] && cat "$_nfqtmp" >> "$ZAPRET/config.new"
mv "$ZAPRET/config.new" "$ZAPRET/config"
rm -f "$_nfqtmp"

# Keenetic / politika ayarlari
set_kv() {
  key="$1"; val="$2"
  if grep -q "^${key}=" "$ZAPRET/config" 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$ZAPRET/config"
  else
    printf '\n%s=%s\n' "$key" "$val" >> "$ZAPRET/config"
  fi
}

set_kv WS_USER nobody
set_kv FWTYPE iptables
set_kv NFQWS_ENABLE 1
set_kv TPWS_ENABLE 0
set_kv MODE_FILTER none
set_kv FLOWOFFLOAD donttouch
set_kv "IFACE_WAN" "$wan"
set_kv FILTER_MARK 0xffffaaa
grep -q '^AUTOHOSTLIST_DEBUGLOG=' "$ZAPRET/config" 2>/dev/null || set_kv AUTOHOSTLIST_DEBUGLOG 1

mkdir -p "$ZAPRET/ipset" "$KZLP_DIR/backups"
touch "$AUTO_HOSTS" "$AUTO_DEBUG" \
  "$ZAPRET/ipset/zapret-hosts-user-exclude.txt" \
  "$ZAPRET/ipset/zapret-hosts-user.txt"
chown nobody "$AUTO_HOSTS" "$AUTO_DEBUG" 2>/dev/null || true

echo "$tag" > "$VERSION_FILE"
echo "$ISP_ID" > "$KZLP_DIR/installed.isp"

# Eski panelleri kaldir
if [ -f /opt/etc/kzlp/requirements.sh ]; then
  . /opt/etc/kzlp/requirements.sh
  kzlp_remove_legacy_panels
fi

# ndm hook
mkdir -p /opt/etc/ndm/netfilter.d
cat > /opt/etc/ndm/netfilter.d/000-zapret.sh << 'EOF'
#!/bin/sh
[ "$type" = "ip6tables" ] && exit 0
[ "$table" != "mangle" ] && [ "$table" != "nat" ] && exit 0
/opt/zapret/init.d/sysv/zapret restart-fw
exit 0
EOF
chmod +x /opt/etc/ndm/netfilter.d/000-zapret.sh

ln -sf /opt/zapret/init.d/sysv/zapret /opt/etc/init.d/S90-zapret 2>/dev/null || true
chmod +x /opt/etc/init.d/S90-zapret /opt/zapret/init.d/sysv/zapret 2>/dev/null || true

mkdir -p /opt/zapret/init.d/sysv/custom.d
cp -f /opt/zapret/init.d/custom.d.examples.linux/10-keenetic-udp-fix \
  /opt/zapret/init.d/sysv/custom.d/10-keenetic-udp-fix 2>/dev/null || true

if [ ! -x /opt/etc/init.d/S00fix ]; then
  cat > /opt/etc/init.d/S00fix << 'EOF'
#!/bin/sh
case "$1" in
  start) sysctl -w net.netfilter.nf_conntrack_checksum=0 >/dev/null 2>&1 ;;
  stop)  sysctl -w net.netfilter.nf_conntrack_checksum=1 >/dev/null 2>&1 ;;
  *) sysctl -w net.netfilter.nf_conntrack_checksum=0 >/dev/null 2>&1 ;;
esac
EOF
  chmod +x /opt/etc/init.d/S00fix
fi

log "Zapret baslatiliyor..."
/opt/etc/init.d/S90-zapret restart >>"$LOG" 2>&1 || true
sleep 2

if pgrep -f '/opt/zapret/nfq/nfqws' >/dev/null 2>&1; then
  log "nfqws calisiyor"
  set_status "done"
  touch "$DONE"
else
  log "UYARI: nfqws baslamadi — loglari kontrol edin"
  set_status "error"
  exit 1
fi

log "Kurulum tamam ($tag / $(kzlp_isp_label "$ISP_ID"))"
exit 0
