# FractalPulse — Software-Only Prototype Plan

**Scope:** Fully reproduce the FractalPulse pipeline (sensing → features → TinyML → MCU inference → alerting → dashboard) without any physical hardware. Real biosignal datasets replace live sensors, and a Dockerized ESP32/QEMU emulator replaces the physical microcontroller.

---

## 1. Goal for the Prototype Submission

Demonstrate a working, end-to-end, edge-AI health-monitoring pipeline where:
- Real ECG/PPG/IMU data from public research datasets stands in for live sensors ("replay" mode).
- A quantized TinyML model is trained, converted to TFLite Micro, and actually **runs inside an emulated ESP32/Xtensa target in Docker** — not just simulated in Python.
- A web dashboard "plays back" the dataset like a live feed and shows real-time classification, confidence scores, and simulated alerts (vibration/buzzer/BLE events shown as UI/log events instead of physical actuation).

This is achievable in a hackathon timeframe because every stage is software-verifiable and Docker-reproducible; nothing depends on procuring parts, soldering, or firmware flashing to real silicon.

---

## 2. Data Sources (PhysioNet, not Kaggle)

| Signal | Dataset | Source | Use |
|---|---|---|---|
| ECG (arrhythmia) | **MIT-BIH Arrhythmia Database** | PhysioNet (physionet.org/content/mitdb) | R-peak detection, arrhythmia/HRV labels |
| ECG (AFib specific) | **MIT-BIH Atrial Fibrillation Database (afdb)** | PhysioNet | AFib-specific rhythm labels |
| PPG | **BIDMC PPG and Respiration Dataset** or **PPG-DaLiA** | PhysioNet / physionet-hosted | Pulse waveform, HR from PPG, respiration reference |
| Respiration | **BIDMC Respiration** (paired with PPG/ECG) | PhysioNet | Breathing rate ground truth |
| Motion / Falls | **SisFall** or **MobiFall** | Public research repositories (university-hosted, not Kaggle) | Accelerometer-based fall vs. ADL (activities of daily living) classification |

**Licensing note:** All PhysioNet datasets are open-access (ODC-BY / PhysioNet Credentialed or Open license depending on set). Cite dataset + PhysioNet in the submission per their required attribution — this is a legal/attribution requirement, not optional.

**Data acquisition tasks:**
1. Download raw WFDB-format records via the `wfdb` Python package (`wfdb.rdrecord`), no manual dataset conversion needed.
2. Store raw signals in `data/raw/` (git-ignored — datasets are large); commit only a small sampled subset for CI/demo speed.
3. Write a `scripts/fetch_data.py` that pulls the exact record IDs used, so the whole pipeline is reproducible from scratch.

---

## 3. Software Architecture (No Hardware)

```
┌─────────────────────┐
│ PhysioNet Datasets   │  (ECG, PPG, IMU/fall records)
└──────────┬───────────┘
           │ replay at real-time rate
           ▼
┌─────────────────────┐
│ Signal Replay Service │  Python (FastAPI/WebSocket) — emulates sensor stream
└──────────┬───────────┘
           │ streams samples
           ▼
┌─────────────────────┐
│ Feature Extraction    │  Python (offline, for training) +
│                        │  C firmware module (on-device, same math, unit-tested for parity)
└──────────┬───────────┘
           ▼
┌─────────────────────┐
│ TinyML Model           │  Trained in Python (TF/Keras) → quantized → TFLite Micro
└──────────┬───────────┘
           ▼
┌─────────────────────────────┐
│ Emulated ESP32 Firmware       │  Runs in QEMU (Xtensa) inside Docker
│  - reads streamed features     │
│  - runs TFLite Micro inference │
│  - emits classification + alert flag over serial/socket
└──────────┬───────────────────┘
           ▼
┌─────────────────────┐
│ Web Dashboard          │  React/Flask — shows live waveform, classification,
│                        │  confidence, simulated alert (vibration/buzzer/BLE icon)
└─────────────────────┘
```

Everything above runs as Docker Compose services on a laptop. No physical device required at any point.

---

## 4. Emulation Strategy: ESP32 in Docker (No Board)

- Use a **QEMU Xtensa/ESP32 emulation image** (e.g., Espressif's `qemu-xtensa` fork used by ESP-IDF's `idf.py qemu`, or the community `espressif/qemu` Docker image) to boot real compiled ESP-IDF firmware.
- Build firmware with the standard **ESP-IDF Docker image** (`espressif/idf`) — this gives a fully reproducible toolchain without installing anything locally.
- Firmware communicates with the host (replay service / dashboard) via QEMU's serial-over-TCP or a virtual UART, so "sensor data in / alert out" behaves like it would on a real board.
- **Fallback tier (if QEMU/ESP-IDF timing proves too fiddly under hackathon time pressure):** run the identical C inference code as a native Linux binary in a plain Docker container (no emulation), and clearly label this as "MCU logic, x86-compiled" in the demo. This still proves the C/TFLite-Micro code path works; QEMU emulation is the stretch goal for full authenticity.

This satisfies "using Docker Hub for Arduino/ESP32" while being 100% reproducible without buying/flashing hardware.

---

## 5. TinyML Model Track (TensorFlow Lite for Microcontrollers)

1. **Feature engineering (Python, offline):** R-peak/HRV from ECG (using `neurokit2` or `wfdb`+custom detector), pulse features from PPG, breathing rate from respiration channel, fall-signature features (jerk, magnitude, orientation) from IMU datasets.
2. **Model:** small MLP or 1D-CNN (Keras) trained per-task or as a shared multi-head classifier; classes: Normal / Arrhythmia risk / Respiratory distress / Fall event / Motion anomaly.
3. **Compression:** post-training quantization (int8) via TFLite converter; validate accuracy drop is acceptable.
4. **Export:** convert to a C byte array (`xxd -i` or `tflite_to_c`) and drop into the ESP-IDF firmware project alongside `tflite-micro` component.
5. **Parity test:** run the same quantized `.tflite` model in Python (via `tflite-runtime`) and compare outputs against the on-device (QEMU) inference to prove no accuracy regression from the C port — this is an important, demonstrable correctness check for judges.

---

## 6. Demo Flow for Judges

1. Dashboard lets the judge pick a dataset segment (e.g., "AFib episode," "fall event," "normal").
2. Replay service streams the raw signal at real-time (or accelerated) rate over WebSocket.
3. Firmware (in QEMU) ingests it, extracts features, runs inference, and returns a classification + confidence + simulated alert flag.
4. Dashboard renders: live waveform, extracted features, model output, and an alert banner ("⚠ Arrhythmia risk detected — vibration/buzzer/BLE alert simulated") when threshold is exceeded.
5. Event log panel shows locally "stored" anomaly summaries (writes to a local SQLite file), demonstrating the "on-device logging, no cloud" concept even though it's containerized.

---

## 7. Repository Structure (proposed)

```
FractalPulse/
├── data/                     # fetch scripts + small sample subset
│   └── fetch_data.py
├── ml/                       # training pipeline
│   ├── features.py
│   ├── train.py
│   ├── quantize_export.py
│   └── notebooks/
├── firmware/                 # ESP-IDF project
│   ├── main/
│   │   ├── app_main.c
│   │   ├── model_data.c      # exported TFLite Micro model
│   │   └── inference.c
│   └── CMakeLists.txt
├── emulation/
│   ├── Dockerfile.espidf     # build firmware (espressif/idf base image)
│   └── Dockerfile.qemu       # run firmware under QEMU
├── replay_service/           # Python FastAPI/WebSocket streamer
├── dashboard/                # React or simple Flask+HTML dashboard
├── docker-compose.yml
└── FractalPulse_SoftwareOnly_Prototype_Plan.md
```

---

## 8. Timeline (2-Week Hackathon, Software-Only)

**Phase 1 — Data (Days 1–2)**
- Fetch MIT-BIH, BIDMC, SisFall/MobiFall records via `wfdb` + PhysioNet.
- Build the replay/streaming service; validate playback timing.

**Phase 2 — Feature Engineering + Labeling (Days 3–4)**
- Implement R-peak/HRV, PPG pulse features, respiration rate, IMU fall-signature extraction.
- Validate features visually against known labeled events.

**Phase 3 — Model Training + Compression (Days 5–7)**
- Train classifier(s), quantize (int8), export to C array.
- Parity-check Python vs. exported model outputs.

**Phase 4 — Firmware + Emulation (Days 8–10)**
- Build ESP-IDF firmware with TFLite Micro + serial I/O.
- Get it building/running via Docker (`espressif/idf`), boot under QEMU.
- Fallback: native x86 build of same C code if QEMU integration stalls.

**Phase 5 — Dashboard + Alerting UI (Days 11–12)**
- Build replay-driven live dashboard: waveform, classification, confidence, simulated alert banner, event log.

**Phase 6 — Integration, Docker Compose, Demo Polish (Days 13–14)**
- Wire all services together with `docker-compose up`.
- Rehearse demo script; record fallback video in case of live-demo issues.

---

## 9. What's Explicitly *Not* Included (Honest Scope for Judges)

- No physical sensors, no real-time human physiological capture — all "sensing" is replayed recorded data, clearly labeled as such.
- No claim of clinical validation or regulatory clearance (FDA/CE) — framed purely as a research prototype/demo.
- Actuation (vibration/buzzer/BLE) is **simulated in the dashboard UI and firmware log output**, not physically triggered.
- QEMU-based ESP32 timing/power figures are **not representative of real hardware power draw** — power claims from the original proposal are reframed as design targets, not measured results.

---

## 10. Key Risks (Software-Only Track)

| Risk | Mitigation |
|---|---|
| QEMU/ESP-IDF Xtensa emulation setup is unstable/time-consuming | Native x86 Docker fallback for the C inference/firmware logic |
| PhysioNet dataset formats (WFDB) unfamiliar | Use `wfdb` Python package; test loading early (Day 1) |
| Model accuracy poor on compact quantized model | Start with handcrafted features + small MLP before attempting CNN/LSTM |
| Multi-dataset time/label alignment (ECG+PPG+IMU are separate datasets, not one subject) | Present cardiac/respiratory and fall detection as separate demo scenarios rather than one fused live subject, avoid overselling "fusion" |
| Serial/socket comms between replay service and QEMU flaky | Build a simple text/JSON protocol early and test in isolation before full integration |

---

## 11. Attribution Requirements

Must cite in submission materials:
- MIT-BIH Arrhythmia Database (Moody & Mark)
- MIT-BIH Atrial Fibrillation Database
- BIDMC PPG and Respiration Dataset
- SisFall / MobiFall dataset authors
- PhysioNet (Goldberger et al., "PhysioBank, PhysioToolkit, and PhysioNet")
