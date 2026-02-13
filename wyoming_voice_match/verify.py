"""Speaker verification using SpeechBrain ECAPA-TDNN."""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import torch
from scipy.spatial.distance import cosine
from speechbrain.inference.speaker import EncoderClassifier

_LOGGER = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result of a speaker verification check."""

    is_match: bool
    similarity: float
    threshold: float
    matched_speaker: Optional[str] = None
    all_scores: Dict[str, float] = field(default_factory=dict)


class SpeakerVerifier:
    """Verifies speaker identity against one or more enrolled voiceprints.

    Uses SpeechBrain's pretrained ECAPA-TDNN model to extract 192-dimensional
    speaker embeddings and compares them via cosine similarity.

    Supports multiple speakers — audio is accepted if any enrolled voice
    matches above the threshold.
    """

    def __init__(
        self,
        voiceprints_dir: str,
        model_dir: str = "/data/models",
        device: str = "cuda",
        threshold: float = 0.30,
        max_verify_seconds: float = 5.0,
        window_seconds: float = 3.0,
        step_seconds: float = 1.5,
    ) -> None:
        self.threshold = threshold
        self.device = device
        self.max_verify_seconds = max_verify_seconds
        self.window_seconds = window_seconds
        self.step_seconds = step_seconds

        # Load the pretrained ECAPA-TDNN model
        run_opts = {"device": device} if device == "cuda" else {}
        self.classifier = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir=f"{model_dir}/spkrec-ecapa-voxceleb",
            run_opts=run_opts,
        )

        # Load all enrolled voiceprints
        self.voiceprints: Dict[str, np.ndarray] = {}
        self._load_voiceprints(voiceprints_dir)

    def _load_voiceprints(self, voiceprints_dir: str) -> None:
        """Load all .npy voiceprint files from the directory."""
        vp_path = Path(voiceprints_dir)
        if not vp_path.exists():
            _LOGGER.warning("Voiceprints directory not found: %s", vp_path)
            return

        for npy_file in sorted(vp_path.glob("*.npy")):
            speaker_name = npy_file.stem
            voiceprint = np.load(str(npy_file))
            self.voiceprints[speaker_name] = voiceprint
            _LOGGER.info(
                "Loaded voiceprint: %s (shape=%s)",
                speaker_name,
                voiceprint.shape,
            )

        if not self.voiceprints:
            _LOGGER.warning(
                "No voiceprints found in %s. "
                "Run the enrollment script first.",
                vp_path,
            )

    def reload_voiceprints(self, voiceprints_dir: str) -> None:
        """Reload voiceprints from disk (e.g., after re-enrollment)."""
        self.voiceprints.clear()
        self._load_voiceprints(voiceprints_dir)

    def verify(self, audio_bytes: bytes, sample_rate: int = 16000) -> VerificationResult:
        """Verify if audio matches any enrolled speaker.

        Uses a two-pass strategy:
        1. First pass: verify only the first MAX_VERIFY_SECONDS of audio
           (where the speaker's voice is most likely to be).
        2. Fallback: if rejected, try a sliding window across the full audio
           to find any segment that matches.

        Full audio is still forwarded to ASR regardless of which window matched.

        Args:
            audio_bytes: Raw PCM audio (16-bit signed little-endian).
            sample_rate: Audio sample rate in Hz.

        Returns:
            VerificationResult with match status, best similarity score,
            matched speaker name, and scores for all enrolled speakers.
        """
        if not self.voiceprints:
            _LOGGER.warning("No voiceprints enrolled — rejecting audio")
            return VerificationResult(
                is_match=False,
                similarity=0.0,
                threshold=self.threshold,
            )

        start_time = time.monotonic()
        bytes_per_second = sample_rate * 2  # 16-bit = 2 bytes per sample
        audio_duration = len(audio_bytes) / bytes_per_second

        # --- Pass 1: verify the first N seconds ---
        max_bytes = int(self.max_verify_seconds * bytes_per_second)
        first_chunk = audio_bytes[:max_bytes]

        _LOGGER.debug(
            "Pass 1: verifying first %.1fs of %.1fs audio",
            len(first_chunk) / bytes_per_second,
            audio_duration,
        )

        result = self._verify_chunk(first_chunk, sample_rate)

        if result.is_match:
            elapsed = (time.monotonic() - start_time) * 1000
            _LOGGER.debug("Pass 1 matched in %.0fms", elapsed)
            return result

        # --- Pass 2: sliding window over full audio ---
        window_bytes = int(self.window_seconds * bytes_per_second)
        step_bytes = int(self.step_seconds * bytes_per_second)

        if len(audio_bytes) > max_bytes and len(audio_bytes) >= window_bytes:
            _LOGGER.debug(
                "Pass 1 rejected (%.4f). Pass 2: sliding %.1fs window "
                "with %.1fs step over %.1fs audio",
                result.similarity,
                self.window_seconds,
                self.step_seconds,
                audio_duration,
            )

            best_result = result
            offset = step_bytes  # skip first window (already checked in pass 1)

            while offset + window_bytes <= len(audio_bytes):
                window = audio_bytes[offset : offset + window_bytes]
                window_result = self._verify_chunk(window, sample_rate)

                if window_result.similarity > best_result.similarity:
                    best_result = window_result

                if window_result.is_match:
                    elapsed = (time.monotonic() - start_time) * 1000
                    window_start = offset / bytes_per_second
                    _LOGGER.debug(
                        "Pass 2 matched at %.1f–%.1fs in %.0fms",
                        window_start,
                        window_start + self.window_seconds,
                        elapsed,
                    )
                    return window_result

                offset += step_bytes

            elapsed = (time.monotonic() - start_time) * 1000
            _LOGGER.debug(
                "Pass 2 finished with no match (best=%.4f) in %.0fms",
                best_result.similarity,
                elapsed,
            )
            return best_result

        elapsed = (time.monotonic() - start_time) * 1000
        _LOGGER.debug("Rejected in %.0fms (%.4f)", elapsed, result.similarity)
        return result

    def _verify_chunk(self, audio_bytes: bytes, sample_rate: int) -> VerificationResult:
        """Verify a single chunk of audio against all enrolled voiceprints."""
        embedding = self._extract_embedding(audio_bytes, sample_rate)

        all_scores: Dict[str, float] = {}
        best_score = -1.0
        best_speaker: Optional[str] = None

        for speaker_name, voiceprint in self.voiceprints.items():
            similarity = 1.0 - cosine(embedding, voiceprint)
            all_scores[speaker_name] = float(similarity)

            if similarity > best_score:
                best_score = similarity
                best_speaker = speaker_name

        is_match = best_score >= self.threshold

        return VerificationResult(
            is_match=is_match,
            similarity=float(best_score),
            threshold=self.threshold,
            matched_speaker=best_speaker if is_match else None,
            all_scores=all_scores,
        )

    def extract_embedding(self, audio_bytes: bytes, sample_rate: int = 16000) -> np.ndarray:
        """Extract a speaker embedding from audio. Public API for enrollment."""
        return self._extract_embedding(audio_bytes, sample_rate)

    def _extract_embedding(self, audio_bytes: bytes, sample_rate: int = 16000) -> np.ndarray:
        """Extract a 192-dimensional speaker embedding from raw PCM audio."""
        # Convert raw PCM bytes to float tensor
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
        audio_np /= 32768.0  # Normalize to [-1.0, 1.0]

        signal = torch.tensor(audio_np).unsqueeze(0)

        if self.device == "cuda":
            signal = signal.to("cuda")

        with torch.no_grad():
            embedding = self.classifier.encode_batch(signal)

        return embedding.squeeze().cpu().numpy()