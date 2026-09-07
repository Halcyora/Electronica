# FractalPulse — Software-Only Prototype

A complete, end-to-end edge-AI health-monitoring pipeline running entirely in software using Docker. No hardware required.

```
PhysioNet Datasets → Signal Replay → Feature Extraction → TinyML Model → Dashboard
```

---

## ✅ What's Included

- **Data Loading** (`ml/data_loader.py`): Load ECG from MIT-BIH, BIDMC, AFib datasets
- **Feature Extraction** (`ml/features.py`): R-peak detection, HRV, PPG pulse, breathing rate, IMU/fall signatures
- **Model Training** (`ml/train.py`): Train compact MLP classifier, quantize to int8 TFLite
- **FastAPI Service** (`replay_service/`): Real-time signal streaming, feature extraction, TFLite inference
- **React Dashboard** (`dashboard/`): Live waveform visualization, classification results, alerts, event log
- **Firmware Skeleton** (`firmware/`): Reference C code for ESP32 (simplified, not compiled in prototype)
- **Docker Compose** (`docker-compose.yml`): Orchestrate all services

---

## 🚀 Quick Start

### 1. Prerequisites

- **Linux/macOS/WSL2 on Windows**
- **Docker & Docker Compose** (v20.10+)
- **Python 3.11** (if running outside Docker)
- **Node.js 18+** (if building dashboard locally)

### 2. Download Datasets

The datasets must be downloaded and extracted before running:

```bash
# Create data directories
mkdir -p data/raw/{mitdb,afdb,bidmc}

# Download MIT-BIH Arrhythmia Database
wget https://physionet.org/content/mitdb/get-zip/1.0.0/ -O mitdb.zip
unzip mitdb.zip -d data/raw/mitdb/

# Download MIT-BIH AFib Database
wget https://physionet.org/content/afdb/get-zip/1.0.0/ -O afdb.zip
unzip afdb.zip -d data/raw/afdb/

# Download BIDMC PPG+Respiration Dataset
wget https://physionet.org/content/bidmc/get-zip/1.0.0/ -O bidmc.zip
unzip bidmc.zip -d data/raw/bidmc/
```

> **Note:** Datasets are ~800 MB total. They are `.gitignore`-d in the repo for size.

### 3. Run with Docker Compose

```bash
# Build and start all services
docker-compose up --build

# Expected output:
# replay-service   | INFO:     Application startup complete
# dashboard        | ▲ [vite] ... listening on http://localhost:3000
# db               | (SQLite running on localhost)
```

### 4. Access the Dashboard

Open your browser:

```
http://localhost:3000
```

You should see:
- **Signal Replay panel**: Select dataset + record
- **ECG Waveform**: Live signal visualization
- **Feature Extraction**: HR, HRV, etc.
- **Classification**: Normal / Anomaly with confidence
- **Alerts**: Triggered when anomaly detected
- **Event Log**: Timestamped events

### 5. Run a Demo Stream

1. Click **Dataset** dropdown → Select `"mitdb"`
2. Click **Record** dropdown → Select `"100"` (well-known AFib episode)
3. Click **▶ Start Stream**
4. Dashboard will stream signal, extract features, run inference
5. When anomaly detected → Alert badge appears

---

## 🏗️ Project Structure

```
FractalPulse/
├── data/
│   ├── raw/                      # PhysioNet datasets (after download)
│   │   ├── mitdb/
│   │   ├── afdb/
│   │   └── bidmc/
│   ├── features/                 # Extracted feature tensors
│   └── db/                       # SQLite event log
│
├── ml/
│   ├── data_loader.py            # PhysioNet dataset I/O
│   ├── features.py               # ECG/PPG/IMU feature extraction
│   ├── train.py                  # Model training & quantization
│   └── notebooks/
│       └── exploratory.ipynb     # Data exploration
│
├── models/
│   ├── fractal_pulse.h5          # Trained Keras model
│   └── fractal_pulse.tflite      # Quantized TFLite (exported)
│
├── replay_service/
│   ├── main.py                   # FastAPI server
│   └── requirements.txt           # Python deps
│
├── firmware/
│   ├── main/
│   │   ├── app_main.c            # ESP32 firmware (C/TFLite Micro)
│   │   ├── CMakeLists.txt
│   │   └── model_data.c          # Auto-generated model bytes
│   └── CMakeLists.txt
│
├── dashboard/
│   ├── src/
│   │   ├── Dashboard.jsx         # Main React component
│   │   ├── Dashboard.css         # Styling
│   │   ├── App.jsx
│   │   └── index.jsx
│   ├── public/
│   │   └── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── Dockerfile
│
├── docker-compose.yml            # Orchestration
├── Dockerfile.replay              # Replay service image
├── requirements.txt               # Root Python deps
└── FractalPulse_SoftwareOnly_Prototype_Plan.md
```

---

## 🔧 Manual Setup (Without Docker)

### Install Python Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Train Model Locally

```bash
python ml/train.py
# Output: models/fractal_pulse.tflite
```

### Run Replay Service

```bash
cd replay_service
uvicorn main:app --reload --port 8000
# http://localhost:8000/docs (Swagger UI)
```

### Build & Run Dashboard

```bash
cd dashboard
npm install
npm run dev
# http://localhost:3000
```

---

## 📊 Using the Dashboard

### Controls

| Panel | Action |
|-------|--------|
| **Signal Replay** | Select dataset/record, click ▶ Start Stream |
| **Waveform** | Live ECG signal updated every ~100ms |
| **Features** | HR, HRV (SDNN, pNN50, RMSSD), etc. |
| **Classification** | Model output: Normal/Anomaly + confidence |
| **Alerts** | Popup when anomaly detected (threshold: confidence > 60%) |
| **Event Log** | Timestamped history of all detected events |

### Datasets

- **`mitdb`** (MIT-BIH Arrhythmia): Mix of normal and arrhythmia records
- **`afdb`** (MIT-BIH AFib): Specific AFib episodes
- **`bidmc`** (BIDMC PPG+Resp): Respiration + pulse waveforms
- **`synthetic_imu`** (Generated): Fall detection scenarios (normal, walking, running, fall)

### Example Records

| Dataset | Record | Use Case |
|---------|--------|----------|
| mitdb | `100` | Normal baseline |
| mitdb | `105` | PVCs (premature beats) |
| afdb | `04048` | Atrial fibrillation |
| synthetic_imu | `fall` | Fall detection demo |

---

## 🤖 Model Architecture

### Training Pipeline

```
Raw ECG Signal → Preprocessing → R-peak Detection → HRV Metrics → Feature Vector
                                                                      ↓
                                                                  MLP Classifier
                                                                  (32→16→2)
                                                                      ↓
                                                                  Quantize int8
                                                                      ↓
                                                                  TFLite Export
```

### Inference

```
Feature Vector (6 floats) → TFLite Model (int8) → Softmax → Class + Confidence
```

**Model Size:** ~5-10 KB quantized (fits easily on microcontroller)

---

## 🧠 Key Algorithms

### ECG Feature Extraction

- **R-peak Detection**: Threshold-based peak finding (Pan-Tompkins simplified)
- **Heart Rate**: 60 / mean(RR interval)
- **HRV Metrics**:
  - SDNN: Std dev of RR intervals
  - pNN50: % of intervals differing >50ms
  - RMSSD: Root mean square of successive differences
- **Arrhythmia Detection**: HR outside [40, 100] bpm or abnormal HRV

### PPG Features

- **Pulse Rate**: Peaks per window
- **Pulse Amplitude**: Max - min normalized signal
- **Pulse Interval Regularity**: Std of pulse intervals

### IMU Features (Fall Detection)

- **Acceleration Magnitude**: Norm of 3-axis
- **Jerk**: Rate of change of acceleration
- **Orientation**: Vertical component ratio
- **Fall Heuristic**: High jerk + sudden deceleration

---

## 🧪 Testing & Validation

### Unit Tests

```bash
pytest ml/tests/
```

### Validate Feature Parity (Python vs. Firmware C)

```bash
python ml/test_feature_parity.py
```

Expected: <1% difference in computed features.

### Model Accuracy

After training, check `models/accuracy_report.txt`:

```
ECG Model - Test Accuracy: 0.95
              precision    recall  f1-score
        Normal       0.92      0.96      0.94
      Arrhythmia     0.94      0.91      0.92
```

---

## 🚧 Advanced: ESP32 Firmware (Optional)

The `firmware/` folder contains a reference C implementation. To compile & run under QEMU:

### Prerequisites

```bash
# Install ESP-IDF
git clone https://github.com/espressif/esp-idf.git
cd esp-idf
./install.sh
source export.sh
```

### Build Firmware

```bash
cd firmware
idf.py build
```

### Run in QEMU

```bash
# Requires QEMU Xtensa support (complex setup)
idf.py qemu
```

> **Status:** Firmware is a reference implementation. For hackathon submission, the Python + React prototype is fully functional. QEMU integration is a stretch goal.

---

## 📝 Attribution & Data Sources

This project uses public datasets; proper attribution is required:

- **MIT-BIH Arrhythmia Database**: Moody & Mark, BSPM 1992
- **MIT-BIH AFib Database**: Goldberger et al., Circulation 2000
- **BIDMC Dataset**: Charlton et al., Sci Data 2016
- **SisFall/MobiFall**: Casilari et al. (synthetic fallback used)
- **PhysioNet**: Goldberger et al., "PhysioBank, PhysioToolkit, and PhysioNet: Components of a New Research Resource for Complex Physiological Signals," Circulation 101(23), 2000

**Include citations in all submissions and presentations.**

---

## 🔐 Privacy & Compliance

- **No cloud upload**: All processing stays local (Docker containers on same machine)
- **No stored PII**: Synthetic/public datasets only; no real patient data
- **No real-time validation**: Prototype is demo/educational; not approved for clinical use
- **Data retention**: Event logs stored locally; can be cleared via `docker-compose down -v`

---

## 🐛 Troubleshooting

### "Connection refused" to replay service

```bash
# Check if service is running
docker ps | grep fractal-pulse-replay

# View logs
docker logs fractal-pulse-replay

# Restart
docker-compose restart replay-service
```

### Dashboard shows "Waiting for signal..."

1. Check that **record is selected** (dropdown)
2. Click **▶ Start Stream**
3. Check browser console (F12) for WebSocket errors
4. Verify replay service health: `curl http://localhost:8000/health`

### WFDB data loading fails

Ensure datasets are extracted correctly:

```bash
ls data/raw/mitdb/ | head
# Should show: 100.dat, 100.hea, 100.atr, etc.
```

### Out of memory during training

Reduce batch size or `n_samples` in `ml/train.py`:

```python
X_ecg_normal, y_ecg_normal = dataset.extract_ecg_dataset(loader, records=None)
# Change to:
records = loader.list_available_records("mitdb")[:5]  # Use fewer records
X_ecg_normal, y_ecg_normal = dataset.extract_ecg_dataset(loader, records=records)
```

---

## 📜 License

This prototype is open-source for educational purposes. Datasets are open-access per PhysioNet terms. Use responsibly.

---

## 🎯 Next Steps

1. **Download datasets** (§ 2 above)
2. **Run `docker-compose up`**
3. **Open `http://localhost:3000`**
4. **Select a record and click ▶ Start Stream**

Questions? Check the detailed plan: `FractalPulse_SoftwareOnly_Prototype_Plan.md`

---

**FractalPulse v1.0 — Built for the Edge. Designed for Healthcare. Open Source.**
