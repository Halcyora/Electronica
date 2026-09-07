"""
Model training and quantization for FractalPulse.
Trains a lightweight MLP classifier on extracted features.
"""

import numpy as np
import pandas as pd
from pathlib import Path
import logging
from typing import Tuple, Dict, List

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score

from ml.data_loader import PhysioNetDataLoader
from ml.features import ECGFeatureExtractor, PPGFeatureExtractor, RespirationFeatureExtractor, IMUFeatureExtractor, generate_synthetic_imu

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class FeatureDataset:
    """Prepare feature dataset for training."""
    
    def __init__(self, output_dir: str = "data/features"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.scaler = StandardScaler()
    
    def extract_ecg_dataset(self, loader: PhysioNetDataLoader, dataset_type: str = "mitdb",
                           records: List[str] = None, window_size_sec: float = 10.0) -> Tuple[np.ndarray, np.ndarray]:
        """
        Extract features from ECG records.
        
        Simple labeling strategy:
        - records with rhythm annotations = arrhythmia (1)
        - normal looking records = normal (0)
        """
        if records is None:
            records = loader.list_available_records(dataset_type)[:10]  # Limit for speed
        
        features_list = []
        labels_list = []
        
        ecg_extractor = ECGFeatureExtractor(fs=250)
        
        for record in records:
            try:
                signal, fs, meta = loader.load_ecg_record(record, dataset=dataset_type)
                
                # For simplicity: take 1-2 windows per record
                n_windows = min(2, len(signal) // (window_size_sec * fs))
                
                for i in range(n_windows):
                    start = i * int(window_size_sec * fs)
                    end = start + int(window_size_sec * fs)
                    
                    if end > len(signal):
                        break
                    
                    window = signal[start:end, 0]  # Use first channel (Lead II typically)
                    
                    # Extract features
                    features = ecg_extractor.extract_features(window)
                    
                    # Simple label: AFib dataset = arrhythmia, MIT-BIH mix
                    label = 1 if dataset_type == "afdb" else 0
                    
                    feature_vec = [features["hr"], features["hrv_sdnn"], features["hrv_pnn50"],
                                  features["hrv_rmssd"], features["hr_mean_rr"], features["arrhythmia_risk"]]
                    
                    features_list.append(feature_vec)
                    labels_list.append(label)
                    
                    logger.info(f"  {record} window {i}: HR={features['hr']:.1f}, label={label}")
            
            except Exception as e:
                logger.warning(f"Skipped {record}: {e}")
        
        X = np.array(features_list, dtype=np.float32)
        y = np.array(labels_list, dtype=np.int32)
        
        logger.info(f"Extracted {len(X)} ECG feature vectors")
        return X, y
    
    def extract_imu_dataset(self, n_samples: int = 100) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate synthetic IMU dataset for fall detection.
        
        Labels:
        - 0: normal/walking
        - 1: fall
        """
        features_list = []
        labels_list = []
        
        imu_extractor = IMUFeatureExtractor(fs=100)
        
        activities = [
            ("normal", 0),
            ("walking", 0),
            ("running", 0),
            ("fall", 1),
        ]
        
        for activity_name, label in activities:
            for i in range(n_samples // 4):
                try:
                    imu_data = generate_synthetic_imu(duration_sec=2.0, activity_type=activity_name)
                    features = imu_extractor.extract_motion_features(imu_data)
                    
                    feature_vec = [
                        features["accel_mean"],
                        features["accel_max"],
                        features["accel_std"],
                        features["jerk_max"],
                        features["orientation_angle"],
                    ]
                    
                    features_list.append(feature_vec)
                    labels_list.append(label)
                
                except Exception as e:
                    logger.warning(f"Failed to generate {activity_name}: {e}")
        
        X = np.array(features_list, dtype=np.float32)
        y = np.array(labels_list, dtype=np.int32)
        
        logger.info(f"Generated {len(X)} IMU feature vectors")
        return X, y


def build_model(input_dim: int, num_classes: int = 2, model_type: str = "mlp") -> keras.Model:
    """Build a lightweight model suitable for microcontroller deployment."""
    
    if model_type == "mlp":
        # Tiny MLP: ~5KB model when quantized
        model = keras.Sequential([
            layers.Input(shape=(input_dim,)),
            layers.Dense(32, activation='relu'),
            layers.Dropout(0.3),
            layers.Dense(16, activation='relu'),
            layers.Dropout(0.2),
            layers.Dense(num_classes, activation='softmax'),
        ])
    
    elif model_type == "tiny_cnn":
        # Would need sequential data input, not applicable here
        raise NotImplementedError("CNN requires different input format")
    
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=0.001),
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy'],
    )
    
    return model


def quantize_model(model: keras.Model, representative_data: np.ndarray) -> bytes:
    """
    Quantize a trained Keras model to int8 TFLite.
    
    Args:
        model: Trained Keras model
        representative_data: Sample data for quantization calibration (shape: (N, input_dim))
    
    Returns:
        TFLite quantized model bytes
    """
    # Convert to concrete function
    run_model = tf.function(lambda x: model(x))
    concrete_func = run_model.get_concrete_function(
        tf.TensorSpec(model.inputs[0].shape, model.inputs[0].dtype)
    )
    
    # Convert to TFLite with quantization
    converter = tf.lite.TFLiteConverter.from_concrete_functions([concrete_func])
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    
    # Provide representative data for quantization
    def representative_dataset():
        for i in range(0, len(representative_data), 10):
            yield [representative_data[i:i+1].astype(np.float32)]
    
    converter.representative_dataset = representative_dataset
    converter.target_spec.supported_ops = [
        tf.lite.OpsSet.TFLITE_BUILTINS_INT8
    ]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8
    
    tflite_model = converter.convert()
    return tflite_model


def export_model_to_c(tflite_model_bytes: bytes, output_file: str = "firmware/main/model_data.c"):
    """
    Export quantized TFLite model as a C byte array for embedding in firmware.
    """
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to hex string
    model_hex = ", ".join(f"0x{byte:02x}" for byte in tflite_model_bytes)
    
    c_code = f"""
// Auto-generated TFLite model for FractalPulse
// Model size: {len(tflite_model_bytes)} bytes
// Generated for embedded deployment

#include <stdint.h>

const uint8_t g_fractal_pulse_model_data[] = {{
    {model_hex}
}};

const size_t g_fractal_pulse_model_data_len = {len(tflite_model_bytes)};
"""
    
    with open(output_path, 'w') as f:
        f.write(c_code)
    
    logger.info(f"Exported model to {output_file} ({len(tflite_model_bytes)} bytes)")


def train_and_export(data_root: str = "data/raw", 
                     model_output: str = "models/fractal_pulse.h5",
                     tflite_output: str = "models/fractal_pulse.tflite",
                     c_header_output: str = "firmware/main/model_data.c"):
    """
    End-to-end: load data, extract features, train model, quantize, export.
    """
    Path(model_output).parent.mkdir(parents=True, exist_ok=True)
    Path(tflite_output).parent.mkdir(parents=True, exist_ok=True)
    
    # Load data
    loader = PhysioNetDataLoader(data_root)
    dataset = FeatureDataset()
    
    logger.info("=" * 60)
    logger.info("TRAINING TRACK 1: ECG/Arrhythmia Detection")
    logger.info("=" * 60)
    
    # Extract ECG features (cardiac anomaly detection)
    X_ecg_normal, y_ecg_normal = dataset.extract_ecg_dataset(loader, dataset_type="mitdb", records=None)
    X_ecg_afib, y_ecg_afib = dataset.extract_ecg_dataset(loader, dataset_type="afdb", records=None)
    
    X_ecg = np.vstack([X_ecg_normal, X_ecg_afib]) if len(X_ecg_afib) > 0 else X_ecg_normal
    y_ecg = np.hstack([y_ecg_normal, y_ecg_afib]) if len(y_ecg_afib) > 0 else y_ecg_normal
    
    if len(X_ecg) > 0:
        X_ecg_train, X_ecg_test, y_ecg_train, y_ecg_test = train_test_split(
            X_ecg, y_ecg, test_size=0.2, random_state=42, stratify=y_ecg if len(np.unique(y_ecg)) > 1 else None
        )
        
        # Scale features
        X_ecg_train_scaled = dataset.scaler.fit_transform(X_ecg_train)
        X_ecg_test_scaled = dataset.scaler.transform(X_ecg_test)
        
        # Train model
        logger.info(f"Training ECG model on {len(X_ecg_train)} samples...")
        model_ecg = build_model(input_dim=X_ecg_train_scaled.shape[1], num_classes=2)
        
        model_ecg.fit(
            X_ecg_train_scaled, y_ecg_train,
            epochs=20,
            batch_size=8,
            validation_split=0.2,
            verbose=1,
        )
        
        # Evaluate
        test_loss, test_acc = model_ecg.evaluate(X_ecg_test_scaled, y_ecg_test, verbose=0)
        y_pred = model_ecg.predict(X_ecg_test_scaled, verbose=0).argmax(axis=1)
        logger.info(f"\nECG Model - Test Accuracy: {test_acc:.3f}")
        logger.info(f"\n{classification_report(y_ecg_test, y_pred, target_names=['Normal', 'Arrhythmia'])}")
        
        # Quantize
        logger.info("Quantizing ECG model...")
        tflite_model = quantize_model(model_ecg, X_ecg_train_scaled)
        
        with open(tflite_output, 'wb') as f:
            f.write(tflite_model)
        logger.info(f"Saved TFLite model: {tflite_output} ({len(tflite_model)} bytes)")
        
        # Export to C
        export_model_to_c(tflite_model, c_header_output)
    
    logger.info("\n" + "=" * 60)
    logger.info("TRAINING TRACK 2: Fall Detection (Synthetic IMU)")
    logger.info("=" * 60)
    
    # Extract IMU features (fall detection)
    X_imu, y_imu = dataset.extract_imu_dataset(n_samples=100)
    
    if len(X_imu) > 0:
        X_imu_train, X_imu_test, y_imu_train, y_imu_test = train_test_split(
            X_imu, y_imu, test_size=0.2, random_state=42
        )
        
        X_imu_train_scaled = StandardScaler().fit_transform(X_imu_train)
        X_imu_test_scaled = StandardScaler().fit_transform(X_imu_test)
        
        logger.info(f"Training IMU model on {len(X_imu_train)} samples...")
        model_imu = build_model(input_dim=X_imu_train_scaled.shape[1], num_classes=2)
        
        model_imu.fit(
            X_imu_train_scaled, y_imu_train,
            epochs=20,
            batch_size=8,
            validation_split=0.2,
            verbose=1,
        )
        
        # Evaluate
        test_loss, test_acc = model_imu.evaluate(X_imu_test_scaled, y_imu_test, verbose=0)
        y_pred = model_imu.predict(X_imu_test_scaled, verbose=0).argmax(axis=1)
        logger.info(f"\nIMU Model - Test Accuracy: {test_acc:.3f}")
        logger.info(f"\n{classification_report(y_imu_test, y_pred, target_names=['Normal', 'Fall'])}")
    
    logger.info("\n" + "=" * 60)
    logger.info("Training complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    train_and_export()
