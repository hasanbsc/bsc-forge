#!/usr/bin/env bash
# BSC Forge - Linux sunucu baslatici.
# Idempotent: ilk acilista Tailscale kurulum/auth yapar, sonraki
# acilislarda mevcut state'i kullanir. Funnel uzerinden public URL acar,
# frontend'i derler ve backend'i baslatir.

set -e

# ===== 0) Proje koku (script'in bulundugu dizin) =====
#   Disk yeniden baglanip mount yolu degisse bile dogru calismasi icin
#   sabit yol yerine script'in kendi konumu kullanilir.
PROJE_KOK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJE_KOK"

# ===== 1) Tailscale kurulu mu? =====
if ! command -v tailscale >/dev/null; then
  echo ""
  echo "============================================================"
  echo "  Tailscale kuruluyor (sudo sifresi istenecek)"
  echo "============================================================"
  curl -fsSL https://tailscale.com/install.sh | sh
fi

# ===== 2) Logged in mi? Degilse interactive auth tetikle =====
if tailscale status 2>&1 | grep -qE "Logged out|NeedsLogin|stopped|NoState"; then
  echo ""
  echo "============================================================"
  echo "  Tailscale auth gerekiyor (sadece ilk acilista bir kez)"
  echo "  Asagida cikacak URL'yi bir tarayicida ac, onayla."
  echo "  Sudo sifren istenebilir."
  echo "============================================================"
  sudo tailscale up --hostname=bsc-forge --operator="$USER" --accept-dns=false
fi

# ===== 3) Funnel kayitlarini sifirla ve yeniden ac =====
#   Tailscale "machine name" (URL'i belirleyen) sadece admin panelden
#   degisir; CLI'dan otomatize edilemiyor. Hostname'i degistirmek icin
#   https://login.tailscale.com/admin/machines uzerinden node'u rename
#   edin. Reset adimi eski hostname'li kayitlari temizler, boylece
#   `funnel status` sadece guncel URL'i listeler.
tailscale funnel reset >/dev/null 2>&1 || true
tailscale funnel --bg 8000 >/dev/null 2>&1 || echo "UYARI: Funnel acilamadi - admin paneldeki ACL'de funnel izni var mi?"

echo ""
echo "--- Funnel durumu ---"
tailscale funnel status 2>&1 || true
echo ""

# ===== 4) Frontend build =====
echo "--- Frontend derleniyor ---"
cd "$PROJE_KOK/frontend"
npm run build
echo ""

# ===== 5) Backend baslat =====
echo "--- Backend baslatiliyor ---"
cd "$PROJE_KOK/backend"
source "$PROJE_KOK/venv/bin/activate"
exec python3 main.py
