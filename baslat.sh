#!/usr/bin/env bash
# BSC Forge - WSL tarafi baslatici.
# .bat tarafindan cagrilir. Idempotent: ilk acilista kurulum/auth yapar,
# sonraki acilislarda mevcut state'i kullanir.

set -e

cd /home/hasan/bsc-forge

# ===== 1) Tailscale WSL'de kurulu mu? =====
if ! command -v tailscale >/dev/null; then
  echo ""
  echo "============================================================"
  echo "  Tailscale WSL'ye kuruluyor (sudo sifresi istenecek)"
  echo "============================================================"
  curl -fsSL https://tailscale.com/install.sh | sh
fi

# ===== 2) Logged in mi? Degilse interactive auth tetikle =====
if tailscale status 2>&1 | grep -qE "Logged out|NeedsLogin|stopped|NoState"; then
  echo ""
  echo "============================================================"
  echo "  Tailscale auth gerekiyor (sadece ilk acilista bir kez)"
  echo "  Asagida cikacak URL'yi Windows tarayicinda ac, onayla."
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

# ===== 5) Frontend build + backend =====
echo "--- Frontend derleniyor ---"
cd frontend
npm run build
echo ""

echo "--- Backend baslatiliyor ---"
cd ../backend
source venv/bin/activate
exec python3 main.py
