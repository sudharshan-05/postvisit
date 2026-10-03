"""
PostVisit AI - Core Tamil Speech-to-Text Module
Model: ai4bharat/indic-conformer-600m-multilingual
"""

import os
import sys
from typing import Dict, Any, Optional
import torch
import torchaudio
import soundfile as sf
from transformers import AutoModel

# Ensure UTF-8 output encoding across Windows consoles
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

if sys.stderr.encoding != 'utf-8':
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Module-level cache so model is only loaded once in memory
_MODEL_CACHE: Dict[str, Any] = {}
DEFAULT_MODEL_ID = "ai4bharat/indic-conformer-600m-multilingual"
TARGET_SAMPLE_RATE = 16000


def get_model(model_name: str = DEFAULT_MODEL_ID):
    """
    Loads and caches the IndicConformer ASR model.
    Reuses cached instance if already loaded.
    """
    if model_name not in _MODEL_CACHE:
        print(f"[ASR] Loading model: {model_name}...")
        model = AutoModel.from_pretrained(
            model_name,
            trust_remote_code=True
        )
        model.eval()
        _MODEL_CACHE[model_name] = model
        print(f"[ASR] Model loaded successfully.")
    return _MODEL_CACHE[model_name]


def preprocess_audio(audio_path: str) -> torch.Tensor:
    """
    Loads and normalizes audio to 1-channel (mono), 16 kHz float tensor.
    Uses soundfile for Windows compatibility without external codec issues.
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Load audio using soundfile (most reliable across Windows installations)
    data, sr = sf.read(audio_path, dtype="float32")
    wav = torch.from_numpy(data)

    # Convert shape to [channels, samples]
    if wav.ndim > 1:
        wav = wav.t()
    else:
        wav = wav.unsqueeze(0)

    # Convert multi-channel (stereo) to mono
    if wav.shape[0] > 1:
        wav = torch.mean(wav, dim=0, keepdim=True)

    # Resample to 16,000 Hz if necessary
    if sr != TARGET_SAMPLE_RATE:
        resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=TARGET_SAMPLE_RATE)
        wav = resampler(wav)

    return wav


def transcribe_audio(
    audio_path: str,
    language: str = "ta",
    strategy: str = "rnnt",
    model_name: str = DEFAULT_MODEL_ID
) -> Dict[str, Any]:
    """
    Transcribes an audio file into text using IndicConformer.

    Args:
        audio_path (str): Path to the WAV/audio file.
        language (str): Target language code ('ta' for Tamil). Default is 'ta'.
        strategy (str): Decoding strategy ('rnnt' or 'ctc'). Default is 'rnnt'.
        model_name (str): Hugging Face model repository ID.

    Returns:
        Dict[str, Any]: {"language": language, "text": transcript, "strategy": strategy}
    """
    try:
        model = get_model(model_name)
        wav = preprocess_audio(audio_path)

        with torch.no_grad():
            output = model(wav, language, decoding=strategy)

        # Output format handling: can be string, list of strings, or dict
        if isinstance(output, (list, tuple)):
            transcript = output[0] if len(output) > 0 else ""
        elif isinstance(output, dict):
            transcript = output.get("text", str(output))
        else:
            transcript = str(output)

        transcript = transcript.strip()

        return {
            "language": language,
            "text": transcript,
            "strategy": strategy
        }

    except Exception as e:
        raise RuntimeError(f"Error transcribing '{audio_path}': {str(e)}") from e
