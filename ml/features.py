"""
Feature extraction for ECG, PPG, and IMU signals.
Includes R-peak detection, HRV, pulse features, breathing rate, and fall signatures.
"""

import numpy as np
from scipy import signal, stats
from scipy.signal import find_peaks
from typing import Tuple, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class ECGFeatureExtractor:
    """Extract cardiac features from ECG signals."""
    
    def __init__(self, fs: float = 250):
        self.fs = fs
    
    def detect_r_peaks(self, ecg_signal: np.ndarray, prominence: float = 0.5) -> np.ndarray:
        """
        Detect R-peaks in ECG using peak finding.
        
        Args:
            ecg_signal: 1D ECG signal (normalized ~[-1, 1])
            prominence: Peak prominence threshold
        
        Returns:
            Indices of detected R-peaks
        """
        # Simple peak detection on normalized signal
        # In practice, would use more sophisticated algorithms (Pan-Tompkins, wavelets)
        peaks, _ = find_peaks(ecg_signal, prominence=prominence, distance=int(0.4 * self.fs))
        return peaks
    
    def compute_heart_rate(self, r_peaks: np.ndarray) -> float:
        """
        Compute instantaneous heart rate from R-peak intervals.
        
        Args:
            r_peaks: Indices of R-peaks
        
        Returns:
            Mean heart rate in beats per minute
        """
        if len(r_peaks) < 2:
            return 0.0
        
        rr_intervals = np.diff(r_peaks) / self.fs  # RR intervals in seconds
        hr_bpm = 60.0 / np.mean(rr_intervals)
        return hr_bpm
    
    def compute_hrv_metrics(self, r_peaks: np.ndarray) -> Dict[str, float]:
        """
        Compute Heart Rate Variability metrics from R-peaks.
        
        Returns:
            Dictionary with HRV features:
            - SDNN: Standard deviation of NN intervals
            - pNN50: Percentage of successive intervals differing >50ms
            - RMSSD: Root mean square of successive differences
        """
        if len(r_peaks) < 3:
            return {"SDNN": 0.0, "pNN50": 0.0, "RMSSD": 0.0}
        
        rr_intervals = np.diff(r_peaks) / self.fs  # in seconds
        rr_ms = rr_intervals * 1000  # convert to milliseconds
        
        sdnn = np.std(rr_ms)
        
        diff_rr = np.diff(rr_ms)
        pnn50 = 100 * np.sum(np.abs(diff_rr) > 50) / len(diff_rr)
        rmssd = np.sqrt(np.mean(diff_rr ** 2))
        
        return {
            "SDNN": float(sdnn),
            "pNN50": float(pnn50),
            "RMSSD": float(rmssd),
            "MeanRR": float(np.mean(rr_ms)),
            "MedianRR": float(np.median(rr_ms)),
        }
    
    def detect_arrhythmia_risk(self, hr: float, hrv: Dict, 
                               hr_min: float = 40, hr_max: float = 100) -> bool:
        """
        Simple heuristic arrhythmia detection.
        Returns True if HR outside normal range or HRV irregular.
        """
        hr_abnormal = hr < hr_min or hr > hr_max
        hrv_abnormal = hrv.get("RMSSD", 0) > 150 or hrv.get("pNN50", 0) > 20  # May indicate AFib
        return hr_abnormal or hrv_abnormal
    
    def extract_features(self, ecg_signal: np.ndarray, window_size_sec: float = 10.0) -> Dict:
        """
        Extract a feature vector from a window of ECG data.
        
        Args:
            ecg_signal: 1D ECG signal
            window_size_sec: Length of analysis window in seconds
        
        Returns:
            Dictionary of extracted features
        """
        window_samples = int(window_size_sec * self.fs)
        if len(ecg_signal) < window_samples:
            ecg_window = ecg_signal
        else:
            ecg_window = ecg_signal[-window_samples:]
        
        # Normalize
        ecg_norm = (ecg_window - np.mean(ecg_window)) / (np.std(ecg_window) + 1e-8)
        
        # Detect peaks
        r_peaks = self.detect_r_peaks(ecg_norm)
        
        # Compute features
        hr = self.compute_heart_rate(r_peaks)
        hrv = self.compute_hrv_metrics(r_peaks)
        arrhythmia_risk = self.detect_arrhythmia_risk(hr, hrv)
        
        return {
            "hr": hr,
            "hrv_sdnn": hrv["SDNN"],
            "hrv_pnn50": hrv["pNN50"],
            "hrv_rmssd": hrv["RMSSD"],
            "hr_mean_rr": hrv["MeanRR"],
            "hr_median_rr": hrv["MedianRR"],
            "arrhythmia_risk": float(arrhythmia_risk),
            "n_beats": len(r_peaks),
        }


class PPGFeatureExtractor:
    """Extract features from PPG (photoplethysmogram) signals."""
    
    def __init__(self, fs: float = 125):
        self.fs = fs
    
    def detect_systolic_peaks(self, ppg_signal: np.ndarray) -> np.ndarray:
        """Detect pulse peaks (systolic peaks) in PPG."""
        peaks, _ = find_peaks(ppg_signal, distance=int(0.4 * self.fs))
        return peaks
    
    def extract_pulse_features(self, ppg_signal: np.ndarray, window_size_sec: float = 10.0) -> Dict:
        """
        Extract features from PPG signal.
        
        Returns:
            - pulse_rate: Heart rate from PPG
            - pulse_amplitude: Peak-to-trough amplitude
            - pulse_interval_regularity: std of pulse intervals
        """
        window_samples = int(window_size_sec * self.fs)
        if len(ppg_signal) < window_samples:
            ppg_window = ppg_signal
        else:
            ppg_window = ppg_signal[-window_samples:]
        
        # Normalize
        ppg_norm = (ppg_window - np.mean(ppg_window)) / (np.std(ppg_window) + 1e-8)
        
        peaks = self.detect_systolic_peaks(ppg_norm)
        
        if len(peaks) < 2:
            return {
                "pulse_rate": 0.0,
                "pulse_amplitude": 0.0,
                "pulse_interval_std": 0.0,
                "n_pulses": 0,
            }
        
        pulse_rate = 60.0 * len(peaks) / (len(ppg_window) / self.fs)
        
        # Amplitude: max - min
        amplitude = np.max(ppg_norm) - np.min(ppg_norm)
        
        # Interval regularity
        pulse_intervals = np.diff(peaks) / self.fs
        interval_std = np.std(pulse_intervals)
        
        return {
            "pulse_rate": float(pulse_rate),
            "pulse_amplitude": float(amplitude),
            "pulse_interval_std": float(interval_std),
            "n_pulses": len(peaks),
        }


class RespirationFeatureExtractor:
    """Extract breathing rate from respiration or PPG modulation."""
    
    def __init__(self, fs: float = 125):
        self.fs = fs
    
    def estimate_breathing_rate(self, respiration_signal: np.ndarray, 
                               window_size_sec: float = 30.0) -> Dict:
        """
        Estimate breathing rate by analyzing low-frequency content.
        Normal breathing: 12-20 breaths/min (0.2-0.33 Hz)
        """
        window_samples = int(window_size_sec * self.fs)
        if len(respiration_signal) < window_samples:
            resp_window = respiration_signal
        else:
            resp_window = respiration_signal[-window_samples:]
        
        # Bandpass filter for respiration frequency (0.1-1 Hz)
        sos = signal.butter(4, [0.1, 1.0], btype='band', fs=self.fs, output='sos')
        resp_filtered = signal.sosfilt(sos, resp_window)
        
        # Detect peaks
        peaks, _ = find_peaks(resp_filtered, distance=int(0.5 * self.fs))
        
        if len(peaks) < 2:
            return {
                "breathing_rate": 0.0,
                "breathing_regularity": 0.0,
                "n_breaths": 0,
            }
        
        breathing_rate = 60.0 * len(peaks) / (len(resp_window) / self.fs)
        
        # Regularity: std of breath intervals
        breath_intervals = np.diff(peaks) / self.fs
        regularity = np.std(breath_intervals) / (np.mean(breath_intervals) + 1e-8)
        
        return {
            "breathing_rate": float(breathing_rate),
            "breathing_regularity": float(regularity),
            "n_breaths": len(peaks),
        }


class IMUFeatureExtractor:
    """Extract motion and fall-related features from accelerometer/IMU data."""
    
    def __init__(self, fs: float = 100):
        self.fs = fs
    
    def compute_acceleration_magnitude(self, accel_3axis: np.ndarray) -> np.ndarray:
        """Compute magnitude of 3-axis acceleration."""
        if accel_3axis.shape[1] != 3:
            raise ValueError("Expected 3-axis accelerometer data")
        
        mag = np.sqrt(np.sum(accel_3axis ** 2, axis=1))
        return mag
    
    def compute_jerk(self, accel_3axis: np.ndarray) -> np.ndarray:
        """Compute jerk (derivative of acceleration)."""
        jerk = np.diff(accel_3axis, axis=0)
        jerk_mag = np.sqrt(np.sum(jerk ** 2, axis=1))
        return jerk_mag
    
    def extract_motion_features(self, accel_3axis: np.ndarray, 
                               window_size_sec: float = 2.0) -> Dict:
        """
        Extract features from IMU (accelerometer/gyro) for motion/fall detection.
        
        Args:
            accel_3axis: Shape (N, 3) — x, y, z acceleration
            window_size_sec: Time window for analysis
        
        Returns:
            Motion feature dictionary
        """
        window_samples = int(window_size_sec * self.fs)
        if len(accel_3axis) < window_samples:
            accel_window = accel_3axis
        else:
            accel_window = accel_3axis[-window_samples:]
        
        # Magnitude
        mag = self.compute_acceleration_magnitude(accel_window)
        mag_mean = np.mean(mag)
        mag_max = np.max(mag)
        mag_std = np.std(mag)
        
        # Jerk
        jerk_mag = self.compute_jerk(accel_window)
        jerk_max = np.max(jerk_mag) if len(jerk_mag) > 0 else 0.0
        
        # Orientation: ratio of vertical component
        vert_axis = 2  # typically Z is vertical
        vert_component = np.abs(accel_window[:, vert_axis])
        orientation_angle = np.mean(vert_component / (mag + 1e-8))
        
        # Fall detection heuristic: high jerk + sudden deceleration
        is_fall_like = (jerk_max > 50) and (mag_max > 50)
        
        return {
            "accel_mean": float(mag_mean),
            "accel_max": float(mag_max),
            "accel_std": float(mag_std),
            "jerk_max": float(jerk_max),
            "orientation_angle": float(orientation_angle),
            "is_fall_like": float(is_fall_like),
        }


# Synthetic fall/ADL generator (fallback if no real dataset available)
def generate_synthetic_imu(duration_sec: float = 10.0, fs: float = 100, 
                          activity_type: str = "walking") -> np.ndarray:
    """
    Generate realistic synthetic IMU data for falls vs. ADL activities.
    
    Args:
        duration_sec: Signal duration
        fs: Sampling frequency
        activity_type: "normal", "walking", "running", "fall"
    
    Returns:
        Shape (N, 3) accelerometer data
    """
    n_samples = int(duration_sec * fs)
    t = np.arange(n_samples) / fs
    
    # Base gravity (9.81 m/s^2, primarily on Z axis when standing)
    accel = np.ones((n_samples, 3)) * 0.1
    accel[:, 2] = 9.81  # Z axis gravity
    
    if activity_type == "normal":
        # Quiet standing with small tremor
        accel[:, 0] += 0.3 * np.sin(2 * np.pi * 0.1 * t)
        accel[:, 1] += 0.3 * np.cos(2 * np.pi * 0.15 * t)
    
    elif activity_type == "walking":
        # Periodic motion at ~1.2 Hz (typical walking cadence)
        accel[:, 0] += 2.0 * np.sin(2 * np.pi * 1.2 * t)
        accel[:, 1] += 1.5 * np.cos(2 * np.pi * 1.2 * t)
        accel[:, 2] += 0.8 * np.sin(2 * np.pi * 2.4 * t)  # Vertical bouncing
    
    elif activity_type == "running":
        # Faster, higher amplitude motion
        accel[:, 0] += 3.5 * np.sin(2 * np.pi * 2.0 * t)
        accel[:, 1] += 3.0 * np.cos(2 * np.pi * 2.0 * t)
        accel[:, 2] += 2.0 * np.sin(2 * np.pi * 4.0 * t)
    
    elif activity_type == "fall":
        # Fall signature: slow descent + impact
        if duration_sec < 2:
            # Slow tilt during fall
            accel[:int(0.8 * n_samples), 2] -= 2.0
            accel[:int(0.8 * n_samples), 0] += 1.5
        else:
            # Descent phase (first 80% of time)
            accel[:int(0.8 * n_samples), 2] -= 2.0
            accel[:int(0.8 * n_samples), 0] += 1.5
            # Impact phase (last 20%): sudden high acceleration
            accel[int(0.8 * n_samples):, :] += np.random.randn(n_samples - int(0.8 * n_samples), 3) * 25
    
    # Add realistic noise
    accel += np.random.randn(n_samples, 3) * 0.5
    
    return accel


if __name__ == "__main__":
    # Test feature extraction
    print("Testing ECG feature extraction...")
    ecg_extractor = ECGFeatureExtractor(fs=250)
    synthetic_ecg = np.sin(2 * np.pi * np.arange(2500) * 1.2 / 250)  # 1.2 Hz beat pattern
    features = ecg_extractor.extract_features(synthetic_ecg)
    print(f"ECG features: {features}")
    
    print("\nTesting IMU feature extraction...")
    imu_extractor = IMUFeatureExtractor(fs=100)
    fall_data = generate_synthetic_imu(duration_sec=2.0, activity_type="fall")
    fall_features = imu_extractor.extract_motion_features(fall_data)
    print(f"Fall features: {fall_features}")
    
    walk_data = generate_synthetic_imu(duration_sec=2.0, activity_type="walking")
    walk_features = imu_extractor.extract_motion_features(walk_data)
    print(f"Walking features: {walk_features}")
