---
description: BSC Forge projesini başlatır — backend (FastAPI) ve frontend (Vite) servislerini ayağa kaldırır.
---

# /baslat

BSC Forge projesini başlat: backend ve frontend'i arka planda çalıştır, sağlık kontrolü yap.

## Adımlar

### 1. Backend

```bash
cd /home/hasan/bsc-forge/backend
```

Sanal ortam yoksa oluştur:

```bash
[ -d venv ] || python3 -m venv venv
```

Bağımlılıkları kur (zaten kuruluysa atlar):

```bash
source venv/bin/activate && pip install -r requirements.txt -q
```

Backend'i başlat:

```bash
source venv/bin/activate && python3 main.py > /tmp/bsc-backend.log 2>&1 &
echo "Backend PID: $!"
```

3 saniye bekle, sağlık kontrolü yap:

```bash
sleep 3 && curl -s http://localhost:8000/
```

### 2. Frontend

```bash
cd /home/hasan/bsc-forge/frontend
```

Bağımlılıkları kur (node_modules yoksa):

```bash
[ -d node_modules ] || npm install -q
```

Frontend'i başlat:

```bash
npm run dev > /tmp/bsc-frontend.log 2>&1 &
echo "Frontend PID: $!"
```

4 saniye bekle, sağlık kontrolü yap:

```bash
sleep 4 && curl -s http://localhost:5173/ | head -3
```

### 3. Özet

Her şey başarılıysa kullanıcıya şunu söyle:

- Backend: http://localhost:8000
- Frontend: http://localhost:5173
- Loglar: `tail -f /tmp/bsc-backend.log` / `tail -f /tmp/bsc-frontend.log`