# FractalPulse — Setup Verification Checklist

Use this checklist to verify that all components are in place and ready to run.

---

## ✅ Pre-Flight Checks

### System Requirements
- [ ] Linux, macOS, or WSL2 on Windows
- [ ] Docker installed (`docker --version`)
- [ ] Docker Compose installed (`docker-compose --version` or `docker compose version`)
- [ ] ~2 GB free disk space for images + containers
- [ ] ~800 MB additional for PhysioNet datasets (optional, can stream)

### Repository Structure
- [ ] All files are in: `c:\Users\P7120483\Downloads\Electronica\`
- [ ] `.gitignore` exists and excludes `data/raw/**`
- [ ] `README.md` is present with usage instructions
- [ ] `docker-compose.yml` is in repo root

---

## 📂 Python Code (ml/)

- [ ] `ml/data_loader.py` — PhysioNet dataset loader ✓
- [ ] `ml/features.py` — Feature extraction (ECG, PPG, IMU) ✓
- [ ] `ml/train.py` — Model training & quantization ✓
- [ ] `requirements.txt` (root) — All Python dependencies ✓

**Verify:**
```bash
grep "wfdb\|tensorflow\|fastapi" requirements.txt
# Should return 3+ matches
```

---

## 🔌 API Service (replay_service/)

- [ ] `replay_service/main.py` — FastAPI app with endpoints ✓
  - [ ] Includes `/datasets` endpoint
  - [ ] Includes `/load_signal` endpoint
  - [ ] Includes `/ws/stream_signal` WebSocket
  - [ ] Includes `/infer` endpoint
  - [ ] Includes `/extract_features` endpoint

- [ ] `Dockerfile.replay` — Service container image ✓
  - [ ] Base: `python:3.11-slim`
  - [ ] Exposes port 8000
  - [ ] Runs `uvicorn replay_service.main:app`

**Verify:**
```bash
grep -E "FastAPI|WebSocket|@app" replay_service/main.py | wc -l
# Should be >= 10
```

---

## 🎨 Dashboard (dashboard/)

- [ ] `dashboard/src/Dashboard.jsx` — Main React component ✓
  - [ ] Includes signal waveform canvas
  - [ ] Includes dataset/record selectors
  - [ ] Includes classification display
  - [ ] Includes alerts panel
  - [ ] Includes event log

- [ ] `dashboard/src/Dashboard.css` — Styling ✓
- [ ] `dashboard/src/App.jsx` — App wrapper ✓
- [ ] `dashboard/src/index.jsx` — React entry point ✓
- [ ] `dashboard/public/index.html` — HTML template ✓
- [ ] `dashboard/package.json` — React dependencies ✓
  - [ ] Includes `react`, `react-dom`
  
- [ ] `dashboard/vite.config.js` — Build config ✓
  - [ ] Port 3000
  - [ ] Plugins: `@vitejs/plugin-react`

- [ ] `dashboard/Dockerfile` — Dashboard container image ✓
  - [ ] Multi-stage build (builder + production)
  - [ ] Exposes port 3000

**Verify:**
```bash
ls -la dashboard/src/*.jsx dashboard/src/*.css dashboard/public/index.html
# Should list 5-6 files
```

---

## 🔧 Docker & Orchestration

- [ ] `docker-compose.yml` — Service definitions ✓
  - [ ] Service: `replay-service` (port 8000)
  - [ ] Service: `dashboard` (port 3000)
  - [ ] Service: `db` (SQLite)
  - [ ] Volumes for data & models
  - [ ] Health checks defined

- [ ] `Dockerfile.replay` — Replay service image ✓

- [ ] `dashboard/Dockerfile` — Dashboard image ✓

**Verify:**
```bash
grep -E "image:|services:|ports:" docker-compose.yml | head -10
# Should show service configuration
```

---

## 🧠 Firmware (Optional)

- [ ] `firmware/main/app_main.c` — ESP32 firmware source ✓
  - [ ] Includes feature extraction functions
  - [ ] Includes TFLite inference loop
  - [ ] Includes alert trigger logic
  - [ ] Includes R-peak detection

- [ ] `firmware/main/CMakeLists.txt` — ESP-IDF build config ✓
- [ ] `firmware/CMakeLists.txt` — Project root build config ✓

**Status:** Reference implementation only (not compiled in prototype)

---

## 📊 Documentation

- [ ] `README.md` — Main usage guide ✓
  - [ ] Quick start instructions
  - [ ] Prerequisites
  - [ ] Dataset download links
  - [ ] Docker Compose instructions
  - [ ] Manual setup (without Docker)
  - [ ] Dashboard usage guide
  - [ ] Attribution & licensing

- [ ] `FractalPulse_SoftwareOnly_Prototype_Plan.md` — Original plan ✓
- [ ] `FractalPulse_Implementation_Summary.md` — This summary ✓
- [ ] `quickstart.sh` — Automated setup script ✓

---

## 📥 Data (Post-Download)

After downloading PhysioNet datasets, verify:

- [ ] `data/raw/mitdb/` contains `.hea`, `.dat`, `.atr` files
  ```bash
  ls data/raw/mitdb | head
  # Should show: 100.hea, 100.dat, 100.atr, etc.
  ```

- [ ] `data/raw/afdb/` contains `.hea`, `.dat`, `.atr` files
- [ ] `data/raw/bidmc/` contains `.hea`, `.dat` files

**Note:** These folders are git-ignored (data not in repo; must download)

---

## 🎯 Pre-Run Checks

### Environment
```bash
cd c:/Users/P7120483/Downloads/Electronica

# Check Python
python3 -m venv test_env
source test_env/bin/activate
pip install tensorflow wfdb fastapi uvicorn  # Should work
deactivate && rm -rf test_env

# Check Node/npm (for dashboard)
node --version      # >= 18
npm --version       # >= 9

# Check Docker
docker --version
docker-compose --version
```

### Lint/Static Checks (Optional)
```bash
# Python syntax
python -m py_compile ml/*.py replay_service/main.py

# JavaScript (if eslint installed)
cd dashboard
npm run lint 2>/dev/null || echo "(Skip if not installed)"
cd ..
```

---

## 🚀 Quick Run Test

### Via Docker Compose
```bash
# Test build
docker-compose build --no-cache 2>&1 | head -20
# Should see "Successfully built" messages

# Start services
timeout 30 docker-compose up 2>&1 || true
# Should see all services starting

# Health check
sleep 10
curl -s http://localhost:8000/health | grep status
# Should return: {"status":"ok"}
```

### Via Local Python (Alternative)
```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Test imports
python -c "import wfdb; import tensorflow; import fastapi; print('✓ All imports OK')"

# Test data loading
python ml/data_loader.py
# Should print: "Found X MIT-BIH records"
```

---

## 📋 File Verification Script

Run this to auto-verify directory structure:

```bash
#!/bin/bash

REQUIRED_FILES=(
    "README.md"
    "requirements.txt"
    "docker-compose.yml"
    "Dockerfile.replay"
    "quickstart.sh"
    "ml/data_loader.py"
    "ml/features.py"
    "ml/train.py"
    "replay_service/main.py"
    "dashboard/src/Dashboard.jsx"
    "dashboard/src/Dashboard.css"
    "dashboard/package.json"
    "dashboard/vite.config.js"
    "dashboard/Dockerfile"
    "firmware/main/app_main.c"
    "firmware/main/CMakeLists.txt"
    ".gitignore"
)

MISSING=0
for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "✓ $file"
    else
        echo "✗ MISSING: $file"
        MISSING=$((MISSING + 1))
    fi
done

if [ $MISSING -eq 0 ]; then
    echo ""
    echo "✅ All files present!"
    exit 0
else
    echo ""
    echo "❌ $MISSING files missing!"
    exit 1
fi
```

Save as `verify.sh` and run:
```bash
bash verify.sh
```

---

## 🟢 Ready to Deploy

Once all checks pass:

```bash
# Final verification
docker-compose config > /dev/null && echo "✓ docker-compose.yml is valid"

# Build & run
bash quickstart.sh

# Or manual:
docker-compose up --build

# Open browser
# http://localhost:3000
```

---

## 🆘 Common Issues

| Issue | Check |
|-------|-------|
| Docker command not found | Install Docker Desktop or Docker Engine |
| `docker-compose: command not found` | Use `docker compose` (v2) instead; update Docker |
| `ModuleNotFoundError` on Python imports | Run inside virtual environment; install `requirements.txt` |
| Port 3000/8000 already in use | Kill processes: `lsof -i :3000` and `kill -9 <PID>` |
| Datasets not found | Ensure `data/raw/mitdb/`, etc. directories exist and contain files |
| Slow initial build | First run builds images (~5-10 min); subsequent runs are faster |
| WebSocket connection errors | Ensure replay-service is healthy: `curl http://localhost:8000/health` |

---

## ✅ Final Sign-Off

- [ ] All files verified ✓
- [ ] Docker images build successfully
- [ ] Services start without errors
- [ ] Dashboard accessible at http://localhost:3000
- [ ] API responds to requests
- [ ] Dataset loading works (or datasets ready to download)
- [ ] Ready to demo to judges ✓

---

**Checklist Status:** Ready to submit! 🎉

*Last updated: 2026-09-08*
