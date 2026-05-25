# KZLP — ISS bazli klasik zapret (nfqws) profilleri
# shellcheck shell=sh

AUTO_HOSTS="/opt/zapret/ipset/zapret-hosts-auto.txt"
AUTO_DEBUG="/opt/zapret/ipset/zapret-hosts-auto-debug.log"
AUTO_OPTS="--hostlist-auto=$AUTO_HOSTS --hostlist-auto-debug=$AUTO_DEBUG"

# $1 = isp id
kzlp_isp_nfqws_opt() {
  case "$1" in
    kablonet|kablofiber|turksat)
      printf '%s\n' \
        "--filter-tcp=80 --hostspell=hoSt --new" \
        "--filter-tcp=443 --dpi-desync=fake --dpi-desync-ttl=2 $AUTO_OPTS --new" \
        "--filter-udp=443 --dpi-desync=fake --dpi-desync-ttl=2"
      ;;
    turktelekom|ttnet)
      printf '%s\n' \
        "--filter-tcp=80 --methodeol --new" \
        "--filter-tcp=443 --dpi-desync=fake --dpi-desync-ttl=2 $AUTO_OPTS --new" \
        "--filter-udp=443 --dpi-desync=fake --dpi-desync-ttl=2"
      ;;
    superonline|sol)
      printf '%s\n' \
        "--filter-tcp=80 --hostspell=hoSt --new" \
        "--filter-tcp=443 --dpi-desync=fake,split2 --dpi-desync-split-pos=1 --dpi-desync-ttl=2 $AUTO_OPTS --new" \
        "--filter-udp=443 --dpi-desync=fake --dpi-desync-ttl=2"
      ;;
    turknet)
      printf '%s\n' \
        "--filter-tcp=80 --hostspell=hoSt --new" \
        "--filter-tcp=443 --dpi-desync=fake --dpi-desync-ttl=3 $AUTO_OPTS --new" \
        "--filter-udp=443 --dpi-desync=fake --dpi-desync-ttl=3"
      ;;
    vodafone)
      printf '%s\n' \
        "--filter-tcp=80 --methodeol --new" \
        "--filter-tcp=443 --dpi-desync=fake --dpi-desync-repeats=6 --dpi-desync-ttl=2 $AUTO_OPTS --new" \
        "--filter-udp=443 --dpi-desync=fake --dpi-desync-repeats=6 --dpi-desync-ttl=2"
      ;;
    generic|*)
      printf '%s\n' \
        "--filter-tcp=80 --hostspell=hoSt --new" \
        "--filter-tcp=443 --dpi-desync=fake --dpi-desync-ttl=2 $AUTO_OPTS --new" \
        "--filter-udp=443 --dpi-desync=fake --dpi-desync-ttl=2"
      ;;
  esac
}

# Oncelikli WAN arayuzu (ISS onerisi)
kzlp_isp_wan_hint() {
  case "$1" in
    kablonet|kablofiber|turksat|turktelekom|ttnet|turknet) echo "ppp0" ;;
    *) echo "" ;;
  esac
}

kzlp_isp_label() {
  case "$1" in
    kablonet) echo "Kablonet" ;;
    kablofiber) echo "Kablonet Fiber (Turksat)" ;;
    turksat) echo "Turksat Kablo" ;;
    turktelekom|ttnet) echo "Turk Telekom" ;;
    superonline|sol) echo "Superonline" ;;
    turknet) echo "TurkNet" ;;
    vodafone) echo "Vodafone" ;;
    generic) echo "Diger / Genel profil" ;;
    *) echo "$1" ;;
  esac
}

valid_isp_id() {
  case "$1" in
    kablonet|kablofiber|turksat|turktelekom|ttnet|superonline|sol|turknet|vodafone|generic)
      return 0 ;;
  esac
  return 1
}
