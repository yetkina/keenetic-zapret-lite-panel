#!/bin/sh
# KZLP API (shell CGI)
export PATH="/opt/sbin:/opt/bin:/opt/usr/sbin:/opt/usr/bin:/sbin:/bin"

KZLP_DIR="/opt/etc/kzlp"
KZLP_VERSION_FILE="$KZLP_DIR/kzlp.version"
ZAPRET_VERSION_FILE="$KZLP_DIR/zapret.version"
ZAPRET="/opt/zapret"
INIT="/opt/etc/init.d/S90-zapret"
EXCLUDE="$ZAPRET/ipset/zapret-hosts-user-exclude.txt"
USER_HOSTS="$ZAPRET/ipset/zapret-hosts-user.txt"
AUTO_HOSTS="$ZAPRET/ipset/zapret-hosts-auto.txt"
AUTO_DEBUG="$ZAPRET/ipset/zapret-hosts-auto-debug.log"
BACKUP_DIR="/opt/etc/kzlp/backups"
POLICY_CHAIN="_NDM_HOTSPOT_PREROUTING_MANGL"
POLICY_MARK="0xffffaaa"
GITHUB_REPO="bol-van/zapret"
KZLP_GITHUB_REPO="yetkina/keenetic-zapret-lite-panel"

POST_BODY=""
if [ "$REQUEST_METHOD" = "POST" ]; then
  read -r POST_BODY
fi

ACTION=""
for pair in $(echo "$QUERY_STRING" | tr '&' ' '); do
  case "$pair" in action=*) ACTION="${pair#action=}" ;; esac
done
if [ -z "$ACTION" ]; then
  ACTION=$(echo "$POST_BODY" | tr '&' '\n' | sed -n 's/^action=//p' | head -1)
fi

post_param() {
  echo "$POST_BODY" | tr '&' '\n' | sed -n "s/^$1=//p" | head -1 | sed 's/+/ /g;s/%/\\x/g' | while read -r _; do :; done
  echo "$POST_BODY" | tr '&' '\n' | sed -n "s/^$1=//p" | head -1
}

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g; s/	/ /g' | tr '\n\r' ' '
}

print_json() {
  printf 'Content-Type: application/json; charset=utf-8\r\nCache-Control: no-store\r\n\r\n%s\n' "$1"
}

json_ok() {
  print_json "{\"ok\":true,\"data\":$1}"
  exit 0
}

json_err() {
  e=$(json_escape "$1")
  print_json "{\"ok\":false,\"error\":\"$e\"}"
  exit 0
}

zapret_running() {
  pgrep -f '/opt/zapret/nfq/nfqws' >/dev/null 2>&1
}

zapret_installed() {
  [ -x "$ZAPRET/nfq/nfqws" ] && [ -f "$ZAPRET/config" ]
}

detect_wan_iface() {
  wan=$(ip -4 route show default 2>/dev/null | awk '$1=="default" && $2=="dev" {print $3; exit}')
  [ -z "$wan" ] && wan=$(ip -4 route show default 2>/dev/null | awk '{print $3; exit}')
  [ -z "$wan" ] && wan="ppp0"
  echo "$wan"
}

# ndmc ciktisindan yalnizca ANSI kodlarini kaldir (tr -d K kullanmayin — Keenetic bozulur)
ndmc_clean() {
  sed 's/\x1b\[[0-9;?]*[a-zA-Z]//g;s/\r//g'
}

ndmc_version_out() {
  [ -x /bin/ndmc ] || return 0
  LD_LIBRARY_PATH= ndmc -c 'show version' 2>/dev/null | ndmc_clean
}

ndmc_system_out() {
  [ -x /bin/ndmc ] || return 0
  LD_LIBRARY_PATH= ndmc -c 'show system' 2>/dev/null | ndmc_clean
}

detect_keenetic_model() {
  m=""
  _out=$(ndmc_version_out)
  if [ -n "$_out" ]; then
    _model=$(echo "$_out" | awk -F': ' '/^[[:space:]]*model:/{gsub(/^[[:space:]]+/,"",$2); print $2; exit}')
    _hw=$(echo "$_out" | awk -F': ' '/^[[:space:]]*hw_id:/{gsub(/^[[:space:]]+/,"",$2); print $2; exit}')
    _dev=$(echo "$_out" | awk -F': ' '/^[[:space:]]*device:/{gsub(/^[[:space:]]+/,"",$2); print $2; exit}')
    if [ -n "$_model" ]; then
      m="Keenetic $_model"
    elif [ -n "$_dev" ] && [ -n "$_hw" ]; then
      m="Keenetic $_dev ($_hw)"
    else
      _desc=$(echo "$_out" | awk -F': ' '/^[[:space:]]*description:/{gsub(/^[[:space:]]+/,"",$2); print $2; exit}')
      if [ -n "$_desc" ]; then
        m=$(echo "$_desc" | sed 's/^eenetic/Keenetic/')
        case "$m" in Keenetic*) ;; *) m="Keenetic $m" ;; esac
      fi
    fi
  fi
  [ -z "$m" ] && m=$(cat /proc/device-tree/model 2>/dev/null | tr -d '\0')
  case "$m" in
    *KN-1012*|*"N-1012"*) m="Keenetic Hero (N-1012)" ;;
    *KN-1810*) m="Keenetic Giant (KN-1810)" ;;
    *KN-2610*) m="Keenetic Peak (KN-2610)" ;;
    *KN-3410*) m="Keenetic Hopper (KN-3410)" ;;
    *KN-3510*) m="Keenetic Hopper SE (KN-3510)" ;;
  esac
  [ -z "$m" ] && m="Keenetic"
  echo "$m"
}

detect_isp_id() {
  domain=""
  cache="$KZLP_DIR/detected.isp"
  if [ -f /opt/var/run/kzlp_iss.cache ]; then
    domain=$(cat /opt/var/run/kzlp_iss.cache 2>/dev/null | tr -d '[:space:]')
  fi
  if [ -z "$domain" ] && [ -x /bin/ndmc ]; then
    domain=$(LD_LIBRARY_PATH= ndmc -c 'show running-config' 2>/dev/null \
      | grep 'authentication identity' | grep -o '@[^[:space:]]*' | head -1)
    [ -n "$domain" ] && echo "$domain" > /opt/var/run/kzlp_iss.cache 2>/dev/null
  fi
  case "$domain" in
    @ttnet) echo "turktelekom" ;;
    @superonline|@fiber) echo "superonline" ;;
    @vodafone) echo "vodafone" ;;
    @kablofiber) echo "kablofiber" ;;
    @kablonet|@turksat) echo "kablonet" ;;
    @turk.net) echo "turknet" ;;
    *) [ -f "$KZLP_DIR/installed.isp" ] && cat "$KZLP_DIR/installed.isp" 2>/dev/null || echo "generic" ;;
  esac
}

isp_list_json() {
  echo -n '[
{"id":"kablonet","name":"Kablonet (Turksat)"},
{"id":"kablofiber","name":"Kablonet Fiber"},
{"id":"turktelekom","name":"Turk Telekom"},
{"id":"superonline","name":"Superonline"},
{"id":"turknet","name":"TurkNet"},
{"id":"vodafone","name":"Vodafone"},
{"id":"generic","name":"Diger / Genel profil"}
]'
}

valid_isp_id() {
  case "$1" in
    kablonet|kablofiber|turksat|turktelekom|ttnet|superonline|sol|turknet|vodafone|generic)
      return 0 ;;
  esac
  return 1
}

isp_id_to_name() {
  case "$1" in
    kablonet) echo "Kablonet (Turksat)" ;;
    kablofiber) echo "Kablonet Fiber" ;;
    turksat) echo "Turksat Kablo" ;;
    turktelekom|ttnet) echo "Turk Telekom" ;;
    superonline|sol) echo "Superonline" ;;
    turknet) echo "TurkNet" ;;
    vodafone) echo "Vodafone" ;;
    *) echo "Genel profil" ;;
  esac
}

detect_firmware() {
  fw=""
  if [ -x /bin/ndmc ]; then
    fw=$(ndmc_version_out | awk -F': ' '/^[[:space:]]*title:/{gsub(/^[[:space:]]+/,"",$2); print $2; exit}')
  fi
  [ -z "$fw" ] && fw="—"
  echo "$fw"
}

detect_hostname() {
  h=$(ndmc_system_out | awk -F': ' '/^[[:space:]]*hostname:/{gsub(/^[[:space:]]+/,"",$2); print $2; exit}')
  [ -z "$h" ] && h=$(hostname 2>/dev/null)
  echo "$h"
}

detect_lan_ip() {
  ip -4 addr show br0 2>/dev/null | awk '/inet /{print $2; exit}' | cut -d/ -f1
}

system_stats() {
  _load1="0"; _load5="0"; _load15="0"
  read -r _load1 _load5 _load15 _ _ < /proc/loadavg 2>/dev/null
  _mem_used=0; _mem_total=0
  if [ -x /bin/ndmc ]; then
    _memline=$(ndmc_system_out \
      | awk -F': ' '/^[[:space:]]*memory:/{gsub(/^[[:space:]]+/,"",$2); print $2; exit}')
    _mem_used=$(echo "$_memline" | cut -d/ -f1)
    _mem_total=$(echo "$_memline" | cut -d/ -f2)
  fi
  [ -z "$_mem_total" ] || [ "$_mem_total" -eq 0 ] && {
    _mem_total=$(awk '/^MemTotal:/{print $2}' /proc/meminfo 2>/dev/null)
    _mem_free=$(awk '/^MemAvailable:/{print $2}' /proc/meminfo 2>/dev/null)
    [ -z "$_mem_free" ] && _mem_free=$(awk '/^MemFree:/{print $2}' /proc/meminfo 2>/dev/null)
    _mem_used=$((_mem_total - _mem_free))
  }
  _uptime=0
  _uptime=$(awk '{print int($1)}' /proc/uptime 2>/dev/null)
  _disk_pct=0; _disk_used=""; _disk_total=""
  _df=$(df -k /opt 2>/dev/null | tail -1)
  if [ -n "$_df" ]; then
    _disk_total=$(echo "$_df" | awk '{print $2}')
    _disk_used=$(echo "$_df" | awk '{print $3}')
    _disk_pct=$(echo "$_df" | awk '{gsub(/%/,"",$5); print $5}')
  fi
  _cpu_temp=""
  if [ -f /sys/class/thermal/thermal_zone0/temp ]; then
    _t=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null)
    [ -n "$_t" ] && _cpu_temp=$((_t / 1000))
  fi
  echo "${_load1}|${_load5}|${_load15}|${_mem_used}|${_mem_total}|${_uptime}|${_disk_pct}|${_disk_used}|${_disk_total}|${_cpu_temp}"
}

# Gereksinim kontrolleri
REQ_SH="$KZLP_DIR/requirements.sh"
if [ -f "$REQ_SH" ]; then
  . "$REQ_SH"
else
  requirements_json() { echo -n '[]'; }
  requirements_mandatory_ok() { return 0; }
  kzlp_remove_legacy_panels() { return 0; }
fi

CHANGELOG_SH="$KZLP_DIR/changelog-parse.sh"
[ -f "$CHANGELOG_SH" ] && . "$CHANGELOG_SH" || {
  changelog_json_for() { echo '{"version":"","added":[],"fixed":[],"changed":[]}'; }
}

# Eski kurulum: installed.version = zapret surumu
if [ -f "$KZLP_DIR/installed.version" ] && [ ! -f "$ZAPRET_VERSION_FILE" ]; then
  grep -qE '^v[0-9]' "$KZLP_DIR/installed.version" 2>/dev/null && \
    mv "$KZLP_DIR/installed.version" "$ZAPRET_VERSION_FILE" 2>/dev/null
fi

norm_ver() {
  echo "$1" | sed 's/^[vV]//;s/[[:space:]]//g'
}

version_gt() {
  _a=$(norm_ver "$1")
  _b=$(norm_ver "$2")
  [ -z "$_a" ] || [ -z "$_b" ] && return 1
  _hi=$(printf '%s\n%s' "$_a" "$_b" | sort -V | tail -1)
  [ "$_hi" = "$_a" ] && [ "$_a" != "$_b" ]
}

zapret_version() {
  v=$(cat "$ZAPRET_VERSION_FILE" 2>/dev/null | tr -d '\n\r')
  [ -n "$v" ] && echo "$v" || echo "bilinmiyor"
}

kzlp_version() {
  v=$(cat "$KZLP_VERSION_FILE" 2>/dev/null | tr -d '\n\r')
  [ -n "$v" ] && echo "$v" || echo "bilinmiyor"
}

kzlp_github_repo() {
  _repo="$KZLP_GITHUB_REPO"
  if [ -f "$KZLP_DIR/settings.json" ]; then
    _r=$(grep '"kzlp_github_repo"' "$KZLP_DIR/settings.json" 2>/dev/null | sed 's/.*: *"\([^"]*\)".*/\1/')
    [ -n "$_r" ] && _repo="$_r"
  fi
  echo "$_repo"
}

# GitHub etiketi (v1.1.0 veya main)
github_kzlp_latest_tag() {
  _repo=$(kzlp_github_repo)
  _tag=""
  raw=$(curl -fsSL -m 25 -H "User-Agent: KZLP" \
    "https://api.github.com/repos/$_repo/releases/latest" 2>/dev/null) || true
  _tag=$(echo "$raw" | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -1)
  if [ -z "$_tag" ]; then
    raw=$(curl -fsSL -m 25 -H "User-Agent: KZLP" \
      "https://api.github.com/repos/$_repo/tags?per_page=5" 2>/dev/null) || true
    _tag=$(echo "$raw" | sed -n 's/.*"name": *"\([^"]*\)".*/\1/p' | head -1)
  fi
  if [ -z "$_tag" ]; then
    _v=$(curl -fsSL -m 15 "https://raw.githubusercontent.com/$_repo/main/VERSION" 2>/dev/null | tr -d '\r\n ')
    if [ -n "$_v" ]; then
      case "$_v" in v*) _tag="$_v" ;; *) _tag="v$_v" ;; esac
    fi
  fi
  [ -n "$_tag" ] && echo "$_tag" || echo "main"
}

github_kzlp_latest() {
  norm_ver "$(github_kzlp_latest_tag)"
}

KEENETIC_HOSTMAP="/tmp/ndnproxyhostmap.conf"

b64_pad() {
  s="$1"
  r=$((${#s} % 4))
  case "$r" in
    2) printf '%s==' "$s" ;;
    3) printf '%s=' "$s" ;;
    *) printf '%s' "$s" ;;
  esac
}

urldecode_pct() {
  printf '%b' "$(printf '%s' "$1" | sed 's/%/\\x/g')"
}

keenetic_name_decode() {
  b64="$1"
  [ -z "$b64" ] && return 0
  raw=$(printf '%s' "$(b64_pad "$b64")" | base64 -d 2>/dev/null) || return 0
  urldecode_pct "$raw"
}

keenetic_name_by_mac() {
  mac_lc=$(echo "$1" | tr 'A-F' 'a-f')
  [ ! -f "$KEENETIC_HOSTMAP" ] && return 0
  b64=$(awk -v m="$mac_lc" '$1=="host_map" && tolower($3)==m && $2 ~ /^192\.168\./ {print $5; exit}' "$KEENETIC_HOSTMAP" 2>/dev/null)
  keenetic_name_decode "$b64"
}

keenetic_name_by_ip() {
  ip="$1"
  [ ! -f "$KEENETIC_HOSTMAP" ] && return 0
  b64=$(awk -v i="$ip" '$1=="host_map" && $2==i {print $5; exit}' "$KEENETIC_HOSTMAP" 2>/dev/null)
  keenetic_name_decode "$b64"
}

policy_users_json() {
  _tmp="/tmp/kzlp_users.$$"
  : > "$_tmp"
  iptables -t mangle -S "$POLICY_CHAIN" 2>/dev/null | grep -i ffffaaa | grep -i mac | \
  while read -r line; do
    mac=$(echo "$line" | sed -n 's/.*--mac-source \([^ ]*\).*/\1/p' | tr 'a-f' 'A-F')
    [ -z "$mac" ] && continue
    ip=$(awk -v m="$(echo "$mac" | tr 'A-F' 'a-f')" 'tolower($4)==m {print $1; exit}' /proc/net/arp 2>/dev/null)
    name=$(keenetic_name_by_mac "$mac")
    [ -z "$name" ] && [ -n "$ip" ] && name=$(keenetic_name_by_ip "$ip")
    name_esc=$(json_escape "$name")
    printf '{"mac":"%s","ip":"%s","name":"%s"}\n' "$mac" "${ip:-}" "$name_esc" >> "$_tmp"
  done
  echo -n "["
  first=1
  while IFS= read -r row; do
    [ -z "$row" ] && continue
    [ "$first" -eq 0 ] && echo -n ","
    first=0
    echo -n "$row"
  done < "$_tmp"
  echo -n "]"
  rm -f "$_tmp"
}

domains_to_json() {
  domains_file_to_json "$EXCLUDE"
}

domains_file_to_json() {
  _f="$1"
  echo -n "["
  first=1
  if [ -f "$_f" ]; then
    while IFS= read -r d; do
      d=$(echo "$d" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
      [ -z "$d" ] || [ "${d#\#}" != "$d" ] && continue
      echo "$d" | grep -qE '^[0-9.:a-fA-F/]' && continue
      [ "$first" -eq 0 ] && echo -n ","
      first=0
      e=$(json_escape "$d")
      printf '"%s"' "$e"
    done < "$_f"
  fi
  echo -n "]"
}

learning_enabled() {
  grep -q 'hostlist-auto=' "$ZAPRET/config" 2>/dev/null
}

auto_log_tail() {
  _n="${1:-30}"
  if [ ! -f "$AUTO_DEBUG" ]; then
    echo -n '""'
    return
  fi
  tail -n "$_n" "$AUTO_DEBUG" 2>/dev/null | json_escape
}

domain_add_to() {
  _file="$1"
  _dom="$2"
  touch "$_file"
  grep -qFx "$_dom" "$_file" 2>/dev/null || echo "$_dom" >> "$_file"
  chown nobody "$AUTO_HOSTS" 2>/dev/null
  chmod 644 "$_file" 2>/dev/null
}

domain_remove_from() {
  _file="$1"
  _dom="$2"
  _t="/tmp/kzlp_d.$$"
  grep -vFx "$_dom" "$_file" 2>/dev/null > "$_t" && mv "$_t" "$_file"
}

sanitize_domain() {
  d=$(echo "$1" | tr 'A-Z' 'a-z' | sed 's|^https\?://||; s|/.*||; s|^\*\.||' | tr -d ' \r\n\t')
  echo "$d" | grep -qE '^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$' && echo "$d"
}

urldecode() {
  printf '%b' "$(echo "$1" | sed 's/+/ /g; s/%\([0-9A-Fa-f][0-9A-Fa-f]\)/\\x\1/g')"
}

case "$ACTION" in
  status)
    running=false
    zapret_running && running=true
    zinst=false
    zapret_installed && zinst=true
    wan=$(grep '^IFACE_WAN=' "$ZAPRET/config" 2>/dev/null | tail -1 | sed 's/^IFACE_WAN=//;s/"//g' | tr -d '\r\n')
    [ -z "$wan" ] && wan=$(detect_wan_iface)
    wan=$(json_escape "$wan")
    users=$(policy_users_json)
    exc=0
    if [ -f "$EXCLUDE" ]; then
      exc=$(grep -vE '^#|^$|^[0-9.:a-fA-F/]' "$EXCLUDE" 2>/dev/null | wc -l | tr -d ' ')
    fi
    zver=$(zapret_version)
    kver=$(kzlp_version)
    json_ok "{\"running\":$running,\"zapret_installed\":$zinst,\"zapret_version\":\"$zver\",\"kzlp_version\":\"$kver\",\"policy_mode\":true,\"policy_mark\":\"$POLICY_MARK\",\"policy_users\":$users,\"exceptions_count\":$exc,\"wan\":\"$wan\"}"
    ;;
  dashboard_live)
    running=false
    zapret_running && running=true
    zinst=false
    zapret_installed && zinst=true
    wan=$(grep '^IFACE_WAN=' "$ZAPRET/config" 2>/dev/null | tail -1 | sed 's/^IFACE_WAN=//;s/"//g' | tr -d '\r\n')
    [ -z "$wan" ] && wan=$(detect_wan_iface)
    _isp=$(detect_isp_id)
    _ispn=$(isp_id_to_name "$_isp")
    IFS='|' read -r _l1 _l5 _l15 _mu _mt _up _dp _du _dt _ct <<EOF
$(system_stats)
EOF
    _policy_n=0
    _policy_n=$(iptables -t mangle -S "$POLICY_CHAIN" 2>/dev/null | grep -i ffffaaa | grep -ci mac)
    _learned=0
    [ -f "$AUTO_HOSTS" ] && _learned=$(grep -vE '^#|^$' "$AUTO_HOSTS" 2>/dev/null | wc -l | tr -d ' ')
    _lt=false
    pgrep lighttpd >/dev/null 2>&1 && _lt=true
    _ram_pct=0
    [ -n "$_mt" ] && [ "$_mt" -gt 0 ] && _ram_pct=$((_mu * 100 / _mt))
    model=$(json_escape "$(detect_keenetic_model)")
    fw=$(json_escape "$(detect_firmware)")
    host=$(json_escape "$(detect_hostname)")
    wan_e=$(json_escape "$wan")
    lan=$(json_escape "$(detect_lan_ip)")
    isp_e=$(json_escape "$_ispn")
    zver=$(zapret_version)
    kver=$(kzlp_version)
    _ct_json="null"
    [ -n "$_ct" ] && _ct_json="$_ct"
    json_ok "{\"hostname\":\"$host\",\"model\":\"$model\",\"firmware\":\"$fw\",\"wan\":\"$wan_e\",\"lan_ip\":\"$lan\",\"isp\":\"$isp_e\",\"zapret_installed\":$zinst,\"zapret_running\":$running,\"zapret_version\":\"$zver\",\"kzlp_version\":\"$kver\",\"policy_devices\":$_policy_n,\"learned_domains\":$_learned,\"lighttpd\":$_lt,\"load1\":\"$_l1\",\"load5\":\"$_l5\",\"load15\":\"$_l15\",\"ram_used_kb\":${_mu:-0},\"ram_total_kb\":${_mt:-0},\"ram_pct\":$_ram_pct,\"disk_pct\":${_dp:-0},\"disk_used_kb\":${_du:-0},\"disk_total_kb\":${_dt:-0},\"uptime_sec\":${_up:-0},\"cpu_temp_c\":$_ct_json}"
    ;;
  install_info)
    zinst=false
    zapret_installed && zinst=true
    model=$(json_escape "$(detect_keenetic_model)")
    isp=$(detect_isp_id)
    wan=$(json_escape "$(detect_wan_iface)")
    arch=$(json_escape "$(uname -m 2>/dev/null)")
    inst_isp=""
    [ -f "$KZLP_DIR/installed.isp" ] && inst_isp=$(cat "$KZLP_DIR/installed.isp" 2>/dev/null | tr -d '\r\n')
    inst_isp=$(json_escape "$inst_isp")
    _st="idle"
    [ -f /opt/tmp/kzlp_install.status ] && _st=$(cat /opt/tmp/kzlp_install.status 2>/dev/null | tr -d '\r\n')
    _st=$(json_escape "$_st")
    _req_ok=false
    requirements_mandatory_ok 2>/dev/null && _req_ok=true
    _req=$(requirements_json 2>/dev/null)
    [ -z "$_req" ] && _req='[]'
    json_ok "{\"zapret_installed\":$zinst,\"model\":\"$model\",\"arch\":\"$arch\",\"detected_isp\":\"$isp\",\"installed_isp\":\"$inst_isp\",\"wan\":\"$wan\",\"isps\":$(isp_list_json),\"install_status\":\"$_st\",\"requirements_ok\":$_req_ok,\"requirements\":$_req}"
    ;;
  install_start)
    kzlp_remove_legacy_panels 2>/dev/null
    requirements_mandatory_ok 2>/dev/null || json_err "Zorunlu bilesenler eksik (Gereksinimler listesine bakin)"
    isp=$(urldecode "$(post_param isp)")
    [ -z "$isp" ] && isp=$(detect_isp_id)
    valid_isp_id "$isp" || json_err "Gecersiz ISS"
    if [ -f /opt/tmp/kzlp_install.status ] && [ "$(cat /opt/tmp/kzlp_install.status 2>/dev/null)" = "running" ]; then
      json_err "Kurulum zaten calisiyor"
    fi
    mkdir -p "$KZLP_DIR" /opt/tmp
    inst="$KZLP_DIR/zapret-install.sh"
    [ -x "$inst" ] || json_err "Kurulum scripti yok. Panel deploy calistirin: scripts/deploy.sh"
    rm -f /opt/tmp/kzlp_install.done
    echo "running" > /opt/tmp/kzlp_install.status
    : > /opt/tmp/kzlp_install.log
    ( "$inst" "$isp" >> /opt/tmp/kzlp_install.log 2>&1 ) &
    json_ok "{\"started\":true,\"isp\":\"$isp\"}"
    ;;
  install_status)
    st="idle"
    [ -f /opt/tmp/kzlp_install.status ] && st=$(cat /opt/tmp/kzlp_install.status 2>/dev/null | tr -d '\r\n')
    log=""
    [ -f /opt/tmp/kzlp_install.log ] && log=$(tail -n 80 /opt/tmp/kzlp_install.log 2>/dev/null | json_escape)
    zinst=false
    zapret_installed && zinst=true
    json_ok "{\"status\":\"$st\",\"log_tail\":\"$log\",\"zapret_installed\":$zinst}"
    ;;
  control)
    zapret_installed || json_err "Zapret kurulu degil"
    cmd=$(urldecode "$(post_param cmd)")
    case "$cmd" in
      start|stop|restart) ;;
      *) json_err "Gecersiz komut" ;;
    esac
    out=$($INIT "$cmd" 2>&1)
    sleep 1
    running=false
    zapret_running && running=true
    o=$(json_escape "$out")
    json_ok "{\"running\":$running,\"output\":\"$o\"}"
    ;;
  version_check)
    raw=$(curl -fsSL -m 25 -H "User-Agent: KZLP" "https://api.github.com/repos/$GITHUB_REPO/releases/latest" 2>/dev/null) \
      || json_err "GitHub erisilemedi"
    tag=$(echo "$raw" | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -1)
    cur=$(zapret_version)
    ua=false
    version_gt "$tag" "$cur" && ua=true
    json_ok "{\"installed\":\"$cur\",\"latest\":\"$tag\",\"update_available\":$ua}"
    ;;
  kzlp_version_check)
    cur=$(kzlp_version)
    latest=$(github_kzlp_latest)
    _tag=$(github_kzlp_latest_tag)
    [ -z "$latest" ] || [ "$latest" = "main" ] && [ "$_tag" = "main" ] && json_err "GitHub surum bilgisi alinamadi"
    ua=false
    version_gt "$latest" "$cur" && ua=true
    _cl=$(changelog_json_for "$(norm_ver "$cur")" "$KZLP_DIR/CHANGELOG.md")
    _cl_latest=$(changelog_json_for "$(norm_ver "$latest")" "$KZLP_DIR/CHANGELOG.md")
    _repo_e=$(json_escape "$(kzlp_github_repo)")
    json_ok "{\"installed\":\"$cur\",\"latest\":\"$latest\",\"latest_tag\":\"$_tag\",\"update_available\":$ua,\"github_repo\":\"$_repo_e\",\"changelog\":$_cl,\"changelog_latest\":$_cl_latest}"
    ;;
  kzlp_update)
    if [ -f /opt/tmp/kzlp_panel_update.status ] && [ "$(cat /opt/tmp/kzlp_panel_update.status 2>/dev/null)" = "running" ]; then
      json_err "Panel guncellemesi zaten calisiyor"
    fi
    latest=$(github_kzlp_latest)
    _tag=$(github_kzlp_latest_tag)
    upd="$KZLP_DIR/kzlp-self-update.sh"
    [ -x "$upd" ] || json_err "Guncelleme scripti yok"
    rm -f /opt/tmp/kzlp_panel_update.done
    echo "running" > /opt/tmp/kzlp_panel_update.status
    : > /opt/tmp/kzlp_panel_update.log
    ( KZLP_GITHUB_REPO="$(kzlp_github_repo)" "$upd" "$_tag" >>/opt/tmp/kzlp_panel_update.log 2>&1 ) &
    json_ok "{\"started\":true,\"target\":\"$latest\",\"tag\":\"$_tag\"}"
    ;;
  kzlp_update_status)
    st="idle"
    [ -f /opt/tmp/kzlp_panel_update.status ] && st=$(cat /opt/tmp/kzlp_panel_update.status 2>/dev/null | tr -d '\r\n')
    log=""
    [ -f /opt/tmp/kzlp_panel_update.log ] && log=$(tail -n 60 /opt/tmp/kzlp_panel_update.log 2>/dev/null | json_escape)
    kv=$(kzlp_version)
    json_ok "{\"status\":\"$st\",\"log_tail\":\"$log\",\"kzlp_version\":\"$kv\"}"
    ;;
  update)
    raw=$(curl -fsSL -m 25 -H "User-Agent: KZLP" "https://api.github.com/repos/$GITHUB_REPO/releases/latest" 2>/dev/null) \
      || json_err "GitHub erisilemedi"
    tag=$(echo "$raw" | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -1)
    url=$(echo "$raw" | tr ',' '\n' | sed -n 's/.*"browser_download_url": *"\([^"]*\)".*/\1/p' | grep '\.tar\.gz' | grep -vE 'openwrt|mips|x86|lexra' | head -1)
    [ -n "$url" ] || json_err "Arsiv bulunamadi"
    tmp="/opt/tmp/kzlp_up_$$"
    mkdir -p "$tmp"
    $INIT stop >/dev/null 2>&1
    curl -fsSL -o "$tmp/z.tgz" "$url" || json_err "Indirme basarisiz"
    tar -xzf "$tmp/z.tgz" -C "$tmp" || json_err "Arsiv acilamadi"
    dir=$(ls -1 "$tmp" | head -1)
    cp -f "$tmp/$dir/nfq/nfqws" "$ZAPRET/nfq/nfqws" && chmod +x "$ZAPRET/nfq/nfqws"
    echo "$tag" > "$ZAPRET_VERSION_FILE"
    $INIT restart >/dev/null 2>&1
    rm -rf "$tmp"
    running=false
    zapret_running && running=true
    json_ok "{\"installed\":\"$tag\",\"running\":$running}"
    ;;
  sites_list)
    _learn=false
    zapret_installed && learning_enabled && _learn=true
    _log=$(auto_log_tail 40)
    json_ok "{\"exclude\":$(domains_file_to_json "$EXCLUDE"),\"user\":$(domains_file_to_json "$USER_HOSTS"),\"learned\":$(domains_file_to_json "$AUTO_HOSTS"),\"learning_enabled\":$_learn,\"log_tail\":\"$_log\"}"
    ;;
  exceptions_list)
    json_ok "{\"domains\":$(domains_file_to_json "$EXCLUDE")}"
    ;;
  exception_add|domain_add)
    dom=$(sanitize_domain "$(urldecode "$(post_param domain)")")
    [ -n "$dom" ] || json_err "Gecersiz domain"
    list=$(urldecode "$(post_param list)")
    [ -z "$list" ] && list="exclude"
    case "$list" in
      exclude) domain_add_to "$EXCLUDE" "$dom" ;;
      user)    domain_add_to "$USER_HOSTS" "$dom" ;;
      *) json_err "Gecersiz liste" ;;
    esac
    $INIT restart-fw >/dev/null 2>&1
    json_ok "{\"exclude\":$(domains_file_to_json "$EXCLUDE"),\"user\":$(domains_file_to_json "$USER_HOSTS"),\"learned\":$(domains_file_to_json "$AUTO_HOSTS")}"
    ;;
  exception_remove|domain_remove)
    dom=$(sanitize_domain "$(urldecode "$(post_param domain)")")
    [ -n "$dom" ] || json_err "Gecersiz domain"
    list=$(urldecode "$(post_param list)")
    [ -z "$list" ] && list="exclude"
    case "$list" in
      exclude) domain_remove_from "$EXCLUDE" "$dom" ;;
      user)    domain_remove_from "$USER_HOSTS" "$dom" ;;
      *) json_err "Gecersiz liste" ;;
    esac
    $INIT restart-fw >/dev/null 2>&1
    json_ok "{\"exclude\":$(domains_file_to_json "$EXCLUDE"),\"user\":$(domains_file_to_json "$USER_HOSTS"),\"learned\":$(domains_file_to_json "$AUTO_HOSTS")}"
    ;;
  learned_clear)
    : > "$AUTO_HOSTS"
    chown nobody "$AUTO_HOSTS" 2>/dev/null
    : > "$AUTO_DEBUG" 2>/dev/null
    json_ok "{\"learned\":[]}"
    ;;
  backup_list)
    mkdir -p "$BACKUP_DIR"
    body='{"backups":['
    first=1
    for f in $(ls -1t "$BACKUP_DIR"/kzlp_*.tar.gz 2>/dev/null); do
      [ "$first" -eq 0 ] && body="$body,"
      first=0
      sz=$(wc -c < "$f" | tr -d ' ')
      mt=$(ls -l "$f" 2>/dev/null | awk '{print $6,$7,$8}')
      body="$body{\"name\":\"$(basename "$f")\",\"size\":$sz,\"mtime\":\"$mt\"}"
    done
    body="$body]}"
    json_ok "$body"
    ;;
  backup_create)
    mkdir -p "$BACKUP_DIR"
    name="kzlp_$(date '+%Y%m%d_%H%M%S').tar.gz"
    path="$BACKUP_DIR/$name"
    tar -czf "$path" "$ZAPRET/config" "$EXCLUDE" "$ZAPRET/ipset/zapret-hosts-user.txt" \
      "$KZLP_DIR/settings.json" "$ZAPRET_VERSION_FILE" "$KZLP_VERSION_FILE" "$KZLP_DIR/CHANGELOG.md" 2>/dev/null \
      || json_err "Yedek olusturulamadi"
    sz=$(wc -c < "$path" | tr -d ' ')
    json_ok "{\"backup\":{\"name\":\"$name\",\"size\":$sz}}"
    ;;
  backup_restore)
    name=$(basename "$(urldecode "$(post_param name)")")
    echo "$name" | grep -qE '^kzlp_[0-9]{8}_[0-9]{6}\.tar\.gz$' || json_err "Gecersiz yedek"
    path="$BACKUP_DIR/$name"
    [ -f "$path" ] || json_err "Yedek yok"
    $INIT stop >/dev/null 2>&1
    tar -xzf "$path" -C / 2>/dev/null || json_err "Geri yukleme hatasi"
    $INIT restart >/dev/null 2>&1
    running=false
    zapret_running && running=true
    json_ok "{\"restored\":\"$name\",\"running\":$running,\"zapret_version\":\"$(zapret_version)\",\"kzlp_version\":\"$(kzlp_version)\"}"
    ;;
  *)
    json_err "Bilinmeyen islem"
    ;;
esac
