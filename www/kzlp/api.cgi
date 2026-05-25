#!/bin/sh
# KZLP API (shell CGI)
export PATH="/opt/sbin:/opt/bin:/opt/usr/sbin:/opt/usr/bin:/sbin:/bin"

KZLP_DIR="/opt/etc/kzlp"
VERSION_FILE="$KZLP_DIR/installed.version"
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

detect_keenetic_model() {
  m=""
  if [ -x /bin/ndmc ]; then
    m=$(LD_LIBRARY_PATH= ndmc -c 'show version' 2>/dev/null | tr -d '\r\033' | tr -d '[]K' \
      | awk -F': ' '/^[[:space:]]*description:/{gsub(/^[[:space:]]+/,"",$2); print $2; exit}')
    [ -z "$m" ] && m=$(LD_LIBRARY_PATH= ndmc -c 'show version' 2>/dev/null | tr -d '\r\033' | tr -d '[]K' \
      | awk -F': ' '/^[[:space:]]*model:/{gsub(/^[[:space:]]+/,"",$2); print "Keenetic "$2; exit}')
  fi
  [ -z "$m" ] && m=$(cat /proc/device-tree/model 2>/dev/null | tr -d '\0')
  [ -z "$m" ] && m="Keenetic"
  m=$(echo "$m" | sed 's/^eenetic/Keenetic/')
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

# Gereksinim kontrolleri
REQ_SH="$KZLP_DIR/requirements.sh"
if [ -f "$REQ_SH" ]; then
  . "$REQ_SH"
else
  requirements_json() { echo -n '[]'; }
  conflicts_json() { echo -n '[]'; }
  requirements_mandatory_ok() { return 0; }
fi

installed_version() {
  v=$(cat "$VERSION_FILE" 2>/dev/null | tr -d '\n\r')
  [ -n "$v" ] && echo "$v" || echo "bilinmiyor"
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
    ver=$(installed_version)
    json_ok "{\"running\":$running,\"zapret_installed\":$zinst,\"installed_version\":\"$ver\",\"policy_mode\":true,\"policy_mark\":\"$POLICY_MARK\",\"policy_users\":$users,\"exceptions_count\":$exc,\"wan\":\"$wan\"}"
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
    _conf=$(conflicts_json 2>/dev/null)
    [ -z "$_conf" ] && _conf='[]'
    json_ok "{\"zapret_installed\":$zinst,\"model\":\"$model\",\"arch\":\"$arch\",\"detected_isp\":\"$isp\",\"installed_isp\":\"$inst_isp\",\"wan\":\"$wan\",\"isps\":$(isp_list_json),\"install_status\":\"$_st\",\"requirements_ok\":$_req_ok,\"requirements\":$_req,\"conflicts\":$_conf}"
    ;;
  install_start)
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
    cur=$(installed_version)
    ua=false
    [ "$cur" != "$tag" ] && ua=true
    json_ok "{\"installed\":\"$cur\",\"latest\":\"$tag\",\"update_available\":$ua}"
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
    echo "$tag" > "$VERSION_FILE"
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
      "$KZLP_DIR/settings.json" "$VERSION_FILE" 2>/dev/null || json_err "Yedek olusturulamadi"
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
    json_ok "{\"restored\":\"$name\",\"running\":$running,\"installed_version\":\"$(installed_version)\"}"
    ;;
  *)
    json_err "Bilinmeyen islem"
    ;;
esac
