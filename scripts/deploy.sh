#!/bin/sh
# KZLP deploy + classic zapret restore
set -e

echo "=== KZLP Deploy ==="

# Stop zapret2 / KZM2 traffic
echo "[1] zapret2 durduruluyor..."
/opt/etc/init.d/S90-zapret2 stop 2>/dev/null || true
chmod -x /opt/etc/init.d/S90-zapret2 2>/dev/null || true
killall nfqws2 2>/dev/null || true

# Restore classic zapret
echo "[2] Classic zapret geri yukleniyor..."
if [ ! -d /opt/zapret ] && [ -d /opt/zapret_classic_backup ]; then
  cp -a /opt/zapret_classic_backup /opt/zapret
fi

if [ ! -d /opt/zapret ]; then
  echo "HATA: /opt/zapret yok"
  exit 1
fi

# Keenetic Zapret policy: yalnizca politikalı cihazlar (mark ffffaaa)
if ! grep -q "^FILTER_MARK=0xffffaaa" /opt/zapret/config 2>/dev/null; then
  echo "" >> /opt/zapret/config
  echo "# Keenetic Zapret policy (KZLP)" >> /opt/zapret/config
  echo "FILTER_MARK=0xffffaaa" >> /opt/zapret/config
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

# Autostart
ln -sf /opt/zapret/init.d/sysv/zapret /opt/etc/init.d/S90-zapret
chmod +x /opt/etc/init.d/S90-zapret /opt/zapret/init.d/sysv/zapret

# keenetic udp fix
mkdir -p /opt/zapret/init.d/sysv/custom.d
cp -f /opt/zapret/init.d/custom.d.examples.linux/10-keenetic-udp-fix \
  /opt/zapret/init.d/sysv/custom.d/10-keenetic-udp-fix 2>/dev/null || true

# S00fix conntrack
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

# KZLP dirs
mkdir -p /opt/etc/kzlp/backups /opt/www/kzlp

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
if [ -f "$REPO_ROOT/www/kzlp/api.cgi" ]; then
  echo "[2b] Panel dosyalari kopyalaniyor..."
  cp -f "$REPO_ROOT/www/kzlp/"* /opt/www/kzlp/
  cp -f "$REPO_ROOT/etc/kzlp/settings.json" /opt/etc/kzlp/
  mkdir -p /opt/etc/lighttpd
  cp -f "$REPO_ROOT/etc/lighttpd/kzlp.conf" /opt/etc/lighttpd/kzlp.conf
  chmod +x /opt/www/kzlp/api.cgi
fi

# Sample exclude hint
EXC=/opt/zapret/ipset/zapret-hosts-user-exclude.txt
touch "$EXC"
if ! grep -q 'turkiye.gov.tr' "$EXC" 2>/dev/null; then
  echo "# KZLP - ornek istisna (panelden duzenleyin)" >> "$EXC"
fi

# lighttpd -> KZLP
echo "[3] lighttpd KZLP..."
killall lighttpd 2>/dev/null || true
mkdir -p /opt/etc/lighttpd
if [ -f /opt/etc/lighttpd/kzlp.conf ]; then
  cp -f /opt/etc/lighttpd/kzlp.conf /opt/etc/lighttpd/lighttpd.conf
else
  echo "WARN: kzlp.conf yok, manuel kontrol"
fi

cat > /opt/etc/init.d/S80lighttpd << 'EOF'
#!/bin/sh
CONF=/opt/etc/lighttpd/lighttpd.conf
case "$1" in
  start)   lighttpd -f "$CONF" ;;
  stop)    kill $(cat /opt/var/run/lighttpd.pid 2>/dev/null) 2>/dev/null; true ;;
  restart) $0 stop; sleep 1; $0 start ;;
esac
EOF
chmod +x /opt/etc/init.d/S80lighttpd
/opt/etc/init.d/S80lighttpd start 2>/dev/null || lighttpd -f /opt/etc/lighttpd/lighttpd.conf

# Start classic zapret
echo "[4] zapret baslatiliyor..."
/opt/etc/init.d/S90-zapret restart

sleep 2
echo "=== Sonuc ==="
pgrep -a nfqws || echo "nfqws calismiyor!"
pgrep -a nfqws2 && echo "UYARI: nfqws2 hala var" || true
curl -sI http://127.0.0.1:8088/ | head -3
iptables -t mangle -S POSTROUTING 2>/dev/null | grep NFQUEUE | head -3
echo "Panel: http://$(ip -4 addr show br0 2>/dev/null | awk '/inet/{print $2}' | cut -d/ -f1 | head -1):8088/"
