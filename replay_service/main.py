"""
FastAPI-based signal replay service and inference gateway for FractalPulse.
Streams raw signals in real-time and handles feature extraction + model inference.
"""

import asyncio
import json
import numpy as np
from pathlib import Path
from typing import Optional, Dict, List
import logging

from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import tensorflow as tf

from ml.data_loader import PhysioNetDataLoader
from ml.features import (
    ECGFeatureExtractor, PPGFeatureExtractor, 
    RespirationFeatureExtractor, IMUFeatureExtractor, 
    generate_synthetic_imu
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="FractalPulse Replay & Inference Service")

# CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Models & State
# ============================================================================

class SignalReplayConfig(BaseModel):
    dataset: str  # "mitdb", "afdb", "bidmc", "synthetic_imu"
    record: str
    start_sec: float = 0.0
    duration_sec: float = 30.0
    speed_factor: float = 1.0  # 1.0 = real-time, 2.0 = 2x speed
    channels: Optional[List[int]] = None


class InferenceRequest(BaseModel):
    features: List[float]
    model_type: str = "ecg"  # "ecg", "imu", "ppg"


class InferenceResponse(BaseModel):
    class_idx: int
    class_name: str
    confidence: float
    all_scores: List[float]


# Global replay state
class ReplayState:
    def __init__(self):
        self.loader = PhysioNetDataLoader()
        self.current_signal = None
        self.current_fs = None
        self.current_metadata = {}
        self.current_position = 0
        self.is_playing = False
        self.model_ecg = None
        self.model_imu = None
    
    def load_signal(self, config: SignalReplayConfig):
        """Load a signal based on the replay config."""
        try:
            if config.dataset == "mitdb":
                signal, fs, meta = self.loader.load_ecg_record(config.record, dataset="mitdb")
            elif config.dataset == "afdb":
                signal, fs, meta = self.loader.load_ecg_record(config.record, dataset="afdb")
            elif config.dataset == "bidmc":
                signal, fs, meta = self.loader.load_bidmc_record(config.record)
            elif config.dataset == "synthetic_imu":
                signal = generate_synthetic_imu(duration_sec=config.duration_sec, activity_type=config.record)
                fs = 100
                meta = {"record": config.record, "dataset": "synthetic_imu", "fs": fs}
            else:
                raise ValueError(f"Unknown dataset: {config.dataset}")
            
            # Trim to requested window
            start_sample = int(config.start_sec * fs)
            end_sample = int((config.start_sec + config.duration_sec) * fs)
            self.current_signal = signal[start_sample:end_sample]
            self.current_fs = fs
            self.current_metadata = meta
            self.current_position = 0
            self.is_playing = True
            
            logger.info(f"Loaded signal: {meta['record']} ({self.current_signal.shape})")
            return True
        except Exception as e:
            logger.error(f"Failed to load signal: {e}")
            raise HTTPException(status_code=400, detail=str(e))
    
    def get_next_batch(self, batch_size: int = 10, speed_factor: float = 1.0) -> Optional[np.ndarray]:
        """
        Get the next batch of samples for streaming.
        Accounts for speed_factor: speed_factor > 1.0 = accelerated playback.
        """
        if self.current_signal is None or not self.is_playing:
            return None
        
        # Compute how many samples to skip based on speed_factor
        step = max(1, int(speed_factor))
        end_pos = self.current_position + batch_size * step
        
        if end_pos > len(self.current_signal):
            # Reached end of signal
            self.is_playing = False
            return None
        
        batch = self.current_signal[self.current_position:end_pos:step]
        self.current_position = end_pos
        
        return batch
    
    def load_models(self, tflite_path: str = "models/fractal_pulse.tflite"):
        """Load TFLite models for inference."""
        try:
            if Path(tflite_path).exists():
                interpreter = tf.lite.Interpreter(model_path=tflite_path)
                interpreter.allocate_tensors()
                self.model_ecg = interpreter
                logger.info(f"Loaded TFLite model: {tflite_path}")
            else:
                logger.warning(f"Model not found: {tflite_path}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")


replay_state = ReplayState()


# ============================================================================
# Routes
# ============================================================================

@app.on_event("startup")
async def startup():
    """Load models on startup."""
    replay_state.load_models()
    logger.info("Service started")


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/datasets")
async def list_datasets():
    """List available datasets and records."""
    try:
        mitdb_records = replay_state.loader.list_available_records("mitdb")
        afdb_records = replay_state.loader.list_available_records("afdb")
        bidmc_records = replay_state.loader.list_available_records("bidmc")
        
        return {
            "mitdb": mitdb_records[:10],  # Limit to 10 for brevity
            "afdb": afdb_records[:10],
            "bidmc": bidmc_records[:10],
            "synthetic_imu": ["normal", "walking", "running", "fall"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/load_signal")
async def load_signal(config: SignalReplayConfig):
    """Load a signal for streaming."""
    replay_state.load_signal(config)
    return {
        "status": "loaded",
        "record": config.record,
        "shape": replay_state.current_signal.shape,
        "fs": replay_state.current_fs,
        "metadata": replay_state.current_metadata,
    }


@app.websocket("/ws/stream_signal")
async def websocket_stream_signal(websocket: WebSocket):
    """
    WebSocket endpoint for real-time signal streaming.
    Client sends: {"batch_size": 10, "speed_factor": 1.0}
    Server sends: {"samples": [...], "timestamp": ..., "position": ...}
    """
    await websocket.accept()
    
    try:
        while True:
            # Receive client config
            config = await websocket.receive_json()
            batch_size = config.get("batch_size", 10)
            speed_factor = config.get("speed_factor", 1.0)
            
            # Get next batch
            batch = replay_state.get_next_batch(batch_size, speed_factor)
            
            if batch is None:
                # End of signal
                await websocket.send_json({"status": "end"})
                break
            
            # Convert to list for JSON serialization
            batch_list = batch.tolist() if isinstance(batch, np.ndarray) else batch
            
            response = {
                "status": "data",
                "samples": batch_list,
                "position": replay_state.current_position,
                "fs": replay_state.current_fs,
            }
            
            await websocket.send_json(response)
            
            # Small delay to simulate real-time streaming
            await asyncio.sleep(0.01)
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close(code=1000)


@app.post("/infer", response_model=InferenceResponse)
async def run_inference(request: InferenceRequest):
    """
    Run inference on extracted features.
    Uses TFLite model if available, otherwise returns dummy prediction.
    """
    features = np.array(request.features, dtype=np.float32).reshape(1, -1)
    
    if replay_state.model_ecg is not None and request.model_type == "ecg":
        # Use TFLite model
        try:
            input_details = replay_state.model_ecg.get_input_details()
            output_details = replay_state.model_ecg.get_output_details()
            
            # Rescale for int8
            input_scale, input_zero_point = input_details[0]['quantization']
            scaled_input = (features / input_scale + input_zero_point).astype(np.int8)
            
            replay_state.model_ecg.set_tensor(input_details[0]['index'], scaled_input)
            replay_state.model_ecg.invoke()
            
            output = replay_state.model_ecg.get_tensor(output_details[0]['index'])
            scores = output[0].astype(np.float32)
        except Exception as e:
            logger.warning(f"TFLite inference failed: {e}, using dummy")
            scores = np.array([0.5, 0.5])
    else:
        # Dummy prediction (for demo when model not loaded)
        scores = np.random.dirichlet([1, 1])
    
    # Normalize
    scores = scores / np.sum(scores)
    class_idx = int(np.argmax(scores))
    confidence = float(scores[class_idx])
    
    class_names = {0: "Normal", 1: "Anomaly"}
    
    return InferenceResponse(
        class_idx=class_idx,
        class_name=class_names.get(class_idx, "Unknown"),
        confidence=confidence,
        all_scores=scores.tolist(),
    )


@app.post("/extract_features")
async def extract_features_endpoint(signals: Dict[str, List[float]]):
    """
    Extract features from raw signals.
    Expects: {"ecg": [...], "ppg": [...], "imu": [...]}
    """
    try:
        features_output = {}
        
        if "ecg" in signals and signals["ecg"]:
            ecg_data = np.array(signals["ecg"], dtype=np.float32)
            ecg_extractor = ECGFeatureExtractor(fs=250)
            features_output["ecg"] = ecg_extractor.extract_features(ecg_data)
        
        if "ppg" in signals and signals["ppg"]:
            ppg_data = np.array(signals["ppg"], dtype=np.float32)
            ppg_extractor = PPGFeatureExtractor(fs=125)
            features_output["ppg"] = ppg_extractor.extract_pulse_features(ppg_data)
        
        if "imu" in signals and signals["imu"]:
            # Expecting shape: N x 3 for x, y, z
            imu_data = np.array(signals["imu"], dtype=np.float32)
            if imu_data.ndim == 1:
                imu_data = imu_data.reshape(-1, 3)
            imu_extractor = IMUFeatureExtractor(fs=100)
            features_output["imu"] = imu_extractor.extract_motion_features(imu_data)
        
        return features_output
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
