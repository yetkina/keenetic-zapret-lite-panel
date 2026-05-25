# KZLP — Keenetic OPKG + Entware gereksinim kontrolleri
# shellcheck shell=sh

_kzlp_modprobe() {
  modprobe "$1" 2>/dev/null
}

_kzlp_kmod_present() {
  _m="$1"
  lsmod 2>/dev/null | grep -qE "^${_m}" && return 0
  find /lib/modules -maxdepth 2 -name "${_m}.ko" 2>/dev/null | grep -q .
}

_kzlp_any_kmod() {
  find /lib/modules -maxdepth 2 -name "$1" 2>/dev/null | grep -q .
}

# id label installed mandatory
requirements_json() {
  echo -n '['
  _first=1
  _add() {
    _id="$1"
    _label="$2"
    _ok="$3"
    _mand="$4"
    [ "$_first" -eq 0 ] && echo -n ','
    _first=0
    _inst=false
    [ "$_ok" -eq 1 ] && _inst=true
    _man=false
    [ "$_mand" -eq 1 ] && _man=true
    _le=$(json_escape "$_label")
    printf '{"id":"%s","label":"%s","installed":%s,"mandatory":%s}' "$_id" "$_le" "$_inst" "$_man"
  }

  _ok=0
  [ -d /opt ] && command -v opkg >/dev/null 2>&1 && _ok=1
  _add "opkg" "Open Package desteği (Entware /opt)" "$_ok" 1

  _ok=0
  if _kzlp_any_kmod "ext4.ko" || _kzlp_any_kmod "vfat.ko" || _kzlp_any_kmod "fat.ko" \
     || _kzlp_any_kmod "exfat.ko" || _kzlp_any_kmod "tntfs.ko"; then
    _ok=1
  fi
  _add "kmod_fs" "Dosya sistemleri çekirdek modülleri" "$_ok" 1

  _ok=0
  _kzlp_any_kmod "uvcvideo.ko" && _ok=1
  _add "kmod_usb_video" "USB Video çekirdek modülleri" "$_ok" 0

  _ok=0
  find /lib/modules -maxdepth 2 -name 'snd-usb*.ko' 2>/dev/null | grep -q . && _ok=1
  _add "kmod_usb_audio" "USB Ses çekirdek modülleri" "$_ok" 0

  _ok=0
  _kzlp_kmod_present "xt_multiport" && _kzlp_kmod_present "nfnetlink_queue" && _ok=1
  _add "kmod_netfilter" "Netfilter çekirdek modülleri" "$_ok" 1

  _ok=0
  lsmod 2>/dev/null | grep -qE '^sch_|^cls_' && _ok=1
  _kzlp_any_kmod "sch_ingress.ko" && _ok=1
  _kzlp_any_kmod "sch_htb.ko" && _ok=1
  _kzlp_any_kmod "sch_cake.ko" && _ok=1
  command -v tc >/dev/null 2>&1 && _ok=1
  _add "kmod_tc" "Trafik Kontrol çekirdek modülleri" "$_ok" 1

  _ok=0
  _kzlp_any_kmod "usbip-core.ko" && _ok=1
  _kzlp_any_kmod "usbip-host.ko" && _ok=1
  _add "kmod_usb_ip" "IP üzerinden USB çekirdek modülleri" "$_ok" 0

  _ok=0
  opkg list-installed 2>/dev/null | grep -qE '^xtables-addons' && _ok=1
  _kzlp_any_kmod "xt_condition.ko" && _ok=1
  _kzlp_kmod_present "xt_ipp2p" && _ok=1
  _add "xtables_addons" "Xtables-addons (Netfilter genişletme)" "$_ok" 1

  _ok=0
  find /lib/modules -maxdepth 2 -name 'dvb-usb*.ko' 2>/dev/null | grep -q . && _ok=1
  _add "kmod_usb_dvb" "USB DVB tuner çekirdek modülleri" "$_ok" 0

  _ok=0
  command -v iptables >/dev/null 2>&1 && iptables --version >/dev/null 2>&1 && _ok=1
  _add "iptables" "iptables (Entware)" "$_ok" 1

  _ok=0
  command -v ipset >/dev/null 2>&1 && _ok=1
  _add "ipset" "ipset (Entware)" "$_ok" 1

  _ok=0
  command -v curl >/dev/null 2>&1 && _ok=1
  _add "curl" "curl (indirme / güncelleme)" "$_ok" 1

  _ok=0
  _kzlp_kmod_present "xt_NFQUEUE" && _ok=1
  _add "nfqueue" "NFQUEUE (xt_NFQUEUE)" "$_ok" 1

  echo -n ']'
}

requirements_mandatory_ok() {
  [ -d /opt ] && command -v opkg >/dev/null 2>&1 || return 1
  _kzlp_any_kmod "ext4.ko" || _kzlp_any_kmod "vfat.ko" || _kzlp_any_kmod "exfat.ko" || _kzlp_any_kmod "tntfs.ko" || return 1
  _kzlp_kmod_present "xt_multiport" || return 1
  _kzlp_kmod_present "nfnetlink_queue" || return 1
  lsmod 2>/dev/null | grep -qE '^sch_|^cls_' || _kzlp_any_kmod "sch_cake.ko" || command -v tc >/dev/null 2>&1 || return 1
  opkg list-installed 2>/dev/null | grep -qE '^xtables-addons' || _kzlp_any_kmod "xt_condition.ko" || return 1
  command -v iptables >/dev/null 2>&1 || return 1
  command -v ipset >/dev/null 2>&1 || return 1
  command -v curl >/dev/null 2>&1 || return 1
  _kzlp_kmod_present "xt_NFQUEUE" || return 1
  return 0
}

conflicts_json() {
  echo -n '['
  _first=1
  _conf() {
    _id="$1"
    _label="$2"
    _active=0
    eval "_active=\$3"
    [ "$_first" -eq 0 ] && echo -n ','
    _first=0
    _act=false
    [ "$_active" -eq 1 ] && _act=true
    _le=$(json_escape "$_label")
    printf '{"id":"%s","label":"%s","active":%s}' "$_id" "$_le" "$_act"
  }

  _a=0
  [ -d /opt/www/kzm2 ] && _a=1
  _conf "kzm2" "KZM2 / keenetic-zapret2-manager paneli" "$_a"

  _a=0
  [ -d /opt/www/nfqws-keenetic-web ] || [ -d /opt/www/nfqws-web ] && _a=1
  _conf "nfqws_web" "nfqws-keenetic-web arayüzü" "$_a"

  _a=0
  pgrep -f '/opt/zapret2/nfq2/nfqws2' >/dev/null 2>&1 && _a=1
  pgrep -x nfqws2 >/dev/null 2>&1 && _a=1
  _conf "nfqws2_daemon" "nfqws2 süreci (çalışıyor)" "$_a"

  _a=0
  [ -x /opt/etc/init.d/S90-zapret2 ] 2>/dev/null && _a=1
  [ -x /opt/etc/init.d/S51nfqws2 ] 2>/dev/null && _a=1
  _conf "zapret2_init" "Zapret2 / nfqws2 otomatik başlatma" "$_a"

  echo -n ']'
}
