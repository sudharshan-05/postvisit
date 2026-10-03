"""
PostVisit AI - Multi-Format Audio Extraction and Normalization Module
Supports MP3, MP4 (video container demuxing), WAV, FLAC, OGG, and M4A.
Standardizes audio to 16,000 Hz mono float32 with peak amplitude normalization.
"""

import os
import sys
from pathlib import Path
from typing import Tuple, Optional
import numpy as np
import torch
import torchaudio
import soundfile as sf
import av

# Target standard for clinical speech recognition (IndicConformer)
TARGET_SAMPLE_RATE = 16000
PEAK_TARGET_DB = -1.0  # Normalized peak target


def extract_audio_from_container(file_path: str) -> Tuple[np.ndarray, int]:
    """
    Extracts audio frames from media containers using PyAV or SoundFile.
    Seamlessly handles MP4, MOV, MKV, MP3, WAV, FLAC, etc.
    """
    path_obj = Path(file_path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Media file not found: {file_path}")

    suffix = path_obj.suffix.lower()

    # Direct soundfile decoding for common audio formats
    if suffix in [".wav", ".flac", ".ogg", ".mp3"]:
        try:
            data, sr = sf.read(str(path_obj), dtype="float32")
            return data, sr
        except Exception:
            # Fall back to PyAV if soundfile fails on corrupt or exotic header
            pass

    # PyAV demuxing for video containers (MP4, MKV, MOV) or complex audio streams
    try:
        container = av.open(str(path_obj))
        audio_streams = [s for s in container.streams if s.type == "audio"]
        if not audio_streams:
            raise ValueError(f"No audio stream found in '{file_path}'")

        audio_stream = audio_streams[0]
        resampler = av.AudioResampler(
            format="flt",  # 32-bit float
            layout="mono",
            rate=TARGET_SAMPLE_RATE
        )

        audio_chunks = []
        for frame in container.decode(audio_stream):
            for resampled_frame in resampler.resample(frame):
                audio_chunks.append(resampled_frame.to_ndarray())

        container.close()

        if not audio_chunks:
            raise ValueError(f"Audio stream in '{file_path}' produced no frames.")

        combined_data = np.concatenate(audio_chunks, axis=1).squeeze()
        return combined_data, TARGET_SAMPLE_RATE

    except Exception as e:
        raise RuntimeError(f"Failed to extract audio from '{file_path}': {str(e)}") from e


def normalize_audio(
    audio_data: np.ndarray,
    orig_sr: int,
    target_sr: int = TARGET_SAMPLE_RATE,
    target_peak_db: float = PEAK_TARGET_DB
) -> torch.Tensor:
    """
    Normalizes audio:
    1. Converts to mono 1D float32 tensor.
    2. Resamples to target_sr (16,000 Hz) if needed.
    3. Performs peak volume normalization to target_peak_db.
    """
    # Convert numpy to PyTorch tensor
    if isinstance(audio_data, np.ndarray):
        wav = torch.from_numpy(audio_data).float()
    else:
        wav = audio_data.float()

    # Convert shape to [channels, samples]
    if wav.ndim == 1:
        wav = wav.unsqueeze(0)
    elif wav.ndim == 2:
        if wav.shape[0] > wav.shape[1]:  # [samples, channels]
            wav = wav.t()
        # Mix multi-channel to mono
        if wav.shape[0] > 1:
            wav = torch.mean(wav, dim=0, keepdim=True)

    # Resample if sample rate differs from target
    if orig_sr != target_sr:
        resampler = torchaudio.transforms.Resample(orig_freq=orig_sr, new_freq=target_sr)
        wav = resampler(wav)

    # Peak normalization
    max_val = torch.max(torch.abs(wav))
    if max_val > 1e-6:
        target_amp = 10.0 ** (target_peak_db / 20.0)
        wav = (wav / max_val) * target_amp

    return wav


def load_and_normalize_audio(file_path: str) -> Tuple[torch.Tensor, int]:
    """
    Main entry point: loads any media file (MP3, MP4, WAV), extracts audio,
    resamples to 16 kHz mono, and normalizes volume.
    Returns:
        (torch.Tensor of shape [1, num_samples], 16000)
    """
    raw_data, sample_rate = extract_audio_from_container(file_path)
    normalized_tensor = normalize_audio(raw_data, orig_sr=sample_rate, target_sr=TARGET_SAMPLE_RATE)
    return normalized_tensor, TARGET_SAMPLE_RATE


def save_normalized_wav(file_path: str, output_wav_path: str) -> str:
    """
    Extracts audio from input file, normalizes it, and saves as 16 kHz mono WAV.
    """
    wav, sr = load_and_normalize_audio(file_path)
    out_dir = Path(output_wav_path).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # Write as float32 WAV
    data_np = wav.squeeze(0).numpy()
    sf.write(output_wav_path, data_np, sr, subtype="PCM_16")
    return output_wav_path
