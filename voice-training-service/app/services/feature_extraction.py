from __future__ import annotations

import io
import json
import logging

import numpy as np

logger = logging.getLogger(__name__)


class FeatureExtractor:
    def extract(self, audio_bytes: bytes) -> dict:
        """Extract voice features from audio bytes (MP3). Returns feature dict."""
        try:
            import librosa
            import soundfile as sf
        except ImportError:
            logger.warning("librosa/soundfile not installed, returning empty features")
            return {}

        try:
            buf = io.BytesIO(audio_bytes)
            y, sr = sf.read(buf)
            if y.ndim > 1:
                y = y.mean(axis=1)
            y = y.astype(np.float32)

            # Pitch (F0)
            f0, voiced_flag, _ = librosa.pyin(y, fmin=50, fmax=600, sr=sr)
            f0_clean = f0[~np.isnan(f0)] if f0 is not None else np.array([])
            avg_pitch = float(np.mean(f0_clean)) if len(f0_clean) > 0 else None

            # Speaking rate (approximate via onset detection)
            onsets = librosa.onset.onset_detect(y=y, sr=sr)
            duration = len(y) / sr
            speaking_rate = len(onsets) / (duration / 60.0) if duration > 0 else None

            # Spectral features for tone characterization
            spectral_centroid = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
            spectral_rolloff = float(np.mean(librosa.feature.spectral_rolloff(y=y, sr=sr)))

            # RMS energy
            rms = float(np.mean(librosa.feature.rms(y=y)))

            # Tempo
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)

            tone_profile = {
                "spectral_centroid": round(spectral_centroid, 2),
                "spectral_rolloff": round(spectral_rolloff, 2),
                "rms_energy": round(rms, 6),
                "tempo_bpm": round(float(tempo), 1) if tempo else None,
            }

            return {
                "avg_pitch_hz": round(avg_pitch, 2) if avg_pitch else None,
                "speaking_rate_wpm": round(speaking_rate, 1) if speaking_rate else None,
                "tone_profile": json.dumps(tone_profile),
            }
        except Exception as e:
            logger.error("Feature extraction failed: %s", e)
            return {}
