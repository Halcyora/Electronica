"""
PhysioNet dataset loader.
Handles MIT-BIH Arrhythmia, AFib, and BIDMC PPG datasets.
"""

import os
import numpy as np
import pandas as pd
import wfdb
from pathlib import Path
from typing import Tuple, List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PhysioNetDataLoader:
    """Load and manage PhysioNet datasets for FractalPulse."""
    
    def __init__(self, data_root: str = "data/raw"):
        self.data_root = Path(data_root)
        self.mitdb_path = self.data_root / "mitdb"
        self.afdb_path = self.data_root / "afdb"
        self.bidmc_path = self.data_root / "bidmc"
        
    def list_available_records(self, dataset: str = "mitdb") -> List[str]:
        """List all records in a dataset."""
        if dataset == "mitdb":
            path = self.mitdb_path
        elif dataset == "afdb":
            path = self.afdb_path
        elif dataset == "bidmc":
            path = self.bidmc_path
        else:
            raise ValueError(f"Unknown dataset: {dataset}")
        
        # Find all .hea files (WFDB header files)
        records = []
        for hea_file in path.glob("*.hea"):
            record_name = hea_file.stem
            records.append(record_name)
        
        return sorted(records)
    
    def load_ecg_record(self, record_name: str, dataset: str = "mitdb", 
                        channels: Optional[List[int]] = None) -> Tuple[np.ndarray, float, Dict]:
        """
        Load ECG record from MIT-BIH datasets.
        
        Args:
            record_name: Name of the record (e.g., "100")
            dataset: "mitdb" or "afdb"
            channels: Which channels to load (default: all)
        
        Returns:
            (signal, sampling_rate, metadata)
        """
        if dataset == "mitdb":
            path = self.mitdb_path / record_name
        elif dataset == "afdb":
            path = self.afdb_path / record_name
        else:
            raise ValueError(f"Unknown ECG dataset: {dataset}")
        
        try:
            record = wfdb.rdrecord(str(path))
            signal = record.p_signal
            fs = record.fs
            
            if channels is not None:
                signal = signal[:, channels]
            
            metadata = {
                "record": record_name,
                "dataset": dataset,
                "fs": fs,
                "n_channels": record.n_sig,
                "sig_name": record.sig_name,
                "n_samples": signal.shape[0],
                "duration_sec": signal.shape[0] / fs
            }
            
            logger.info(f"Loaded {dataset}/{record_name}: {metadata['duration_sec']:.1f}s @ {fs}Hz")
            return signal, fs, metadata
        
        except Exception as e:
            logger.error(f"Failed to load {dataset}/{record_name}: {e}")
            raise
    
    def load_bidmc_record(self, record_name: str) -> Tuple[np.ndarray, float, Dict]:
        """
        Load BIDMC PPG + Respiration record.
        
        Returns:
            (signal [ECG, PPG, Resp], sampling_rate, metadata)
        """
        path = self.bidmc_path / record_name
        
        try:
            record = wfdb.rdrecord(str(path))
            signal = record.p_signal
            fs = record.fs
            
            metadata = {
                "record": record_name,
                "dataset": "bidmc",
                "fs": fs,
                "n_channels": record.n_sig,
                "sig_name": record.sig_name,
                "n_samples": signal.shape[0],
                "duration_sec": signal.shape[0] / fs
            }
            
            logger.info(f"Loaded BIDMC/{record_name}: {metadata['duration_sec']:.1f}s @ {fs}Hz, signals: {record.sig_name}")
            return signal, fs, metadata
        
        except Exception as e:
            logger.error(f"Failed to load BIDMC/{record_name}: {e}")
            raise
    
    def load_annotations(self, record_name: str, dataset: str = "mitdb") -> Dict:
        """
        Load annotation file (.atr) for rhythm/beat information.
        
        Returns:
            Dict with sample indices, symbols, and auxiliary info
        """
        if dataset == "mitdb":
            path = self.mitdb_path / record_name
        elif dataset == "afdb":
            path = self.afdb_path / record_name
        else:
            raise ValueError(f"Unknown dataset: {dataset}")
        
        try:
            annotation = wfdb.rdann(str(path), "atr")
            
            result = {
                "sample": annotation.sample.tolist(),
                "symbol": annotation.symbol,
                "aux_note": annotation.aux_note if annotation.aux_note else [],
            }
            
            return result
        except Exception as e:
            logger.warning(f"No annotations found for {dataset}/{record_name}: {e}")
            return {"sample": [], "symbol": [], "aux_note": []}


def get_sample_records(dataset: str = "mitdb", n_samples: int = 5) -> List[str]:
    """Get a small set of representative records for quick testing."""
    # These are well-known, commonly-used records
    sample_map = {
        "mitdb": ["100", "101", "103", "105", "111"],  # Mix of normal, PVCs, AFib
        "afdb": ["04043", "04048", "04126", "04746", "05091"],  # AFib records
        "bidmc": ["BIDMC_CSV/0001", "BIDMC_CSV/0002", "BIDMC_CSV/0003"],  # PPG+resp
    }
    
    return sample_map.get(dataset, [])[:n_samples]


if __name__ == "__main__":
    loader = PhysioNetDataLoader()
    
    # Test MIT-BIH loading
    mitdb_records = loader.list_available_records("mitdb")
    print(f"Found {len(mitdb_records)} MIT-BIH records: {mitdb_records[:5]}")
    
    if mitdb_records:
        try:
            signal, fs, meta = loader.load_ecg_record(mitdb_records[0], dataset="mitdb")
            print(f"✓ Loaded {meta['record']}: {signal.shape}")
        except Exception as e:
            print(f"✗ Load failed: {e}")
    
    # Test BIDMC loading
    bidmc_records = loader.list_available_records("bidmc")
    print(f"\nFound {len(bidmc_records)} BIDMC records: {bidmc_records[:5]}")
    
    if bidmc_records:
        try:
            signal, fs, meta = loader.load_bidmc_record(bidmc_records[0])
            print(f"✓ Loaded {meta['record']}: {signal.shape}")
        except Exception as e:
            print(f"✗ Load failed: {e}")
