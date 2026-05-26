# KZLP CHANGELOG.md -> JSON (shell)
# Kullanim: changelog_json_for 1.0.0 /opt/etc/kzlp/CHANGELOG.md

changelog_json_for() {
  _ver=$(echo "$1" | sed 's/^[vV]//')
  _file="${2:-/opt/etc/kzlp/CHANGELOG.md}"
  [ -f "$_file" ] || _file="$(dirname "$0")/../CHANGELOG.md"
  [ -f "$_file" ] || { echo '{"version":"","added":[],"fixed":[],"changed":[]}'; return; }

  _awk_out=$(awk -v ver="$_ver" '
    BEGIN { found=0; sec=""; added=""; fixed=""; changed="" }
    /^## \[/ {
      if (found) exit
      line=$0
      gsub(/^## \[/,"",line)
      sub(/\].*$/,"",line)
      gsub(/^[vV]/,"",line)
      if (line==ver) found=1
      next
    }
    found && /^### / {
      sec=$0
      gsub(/^### /,"",sec)
      next
    }
    found && /^- / {
      item=$0
      gsub(/^- /,"",item)
      gsub(/"/,"\\\"",item)
      if (sec ~ /Eklendi/) added=added sprintf("\"%s\",",item)
      else if (sec ~ /Duzeltildi|Düzeltildi/) fixed=fixed sprintf("\"%s\",",item)
      else if (sec ~ /Degistirildi|Değiştirildi/) changed=changed sprintf("\"%s\",",item)
      next
    }
    found && /^## \[/ { exit }
    END {
      sub(/,$/,"",added); sub(/,$/,"",fixed); sub(/,$/,"",changed)
      printf "{\"version\":\"%s\",\"added\":[", ver
      if (added=="") printf "]"; else printf "%s]", added
      printf ",\"fixed\":["
      if (fixed=="") printf "]"; else printf "%s]", fixed
      printf ",\"changed\":["
      if (changed=="") printf "]"; else printf "%s]", changed
      printf "}"
    }
  ' "$_file" 2>/dev/null)

  [ -n "$_awk_out" ] && echo "$_awk_out" || echo '{"version":"","added":[],"fixed":[],"changed":[]}'
}
