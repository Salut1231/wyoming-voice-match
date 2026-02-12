"""Speaker verification using SpeechBrain ECAPA-TDNN."""

import logging
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
        threshold: float = 0.45,
    ) -> None:
        self.threshold = threshold
        self.device = device

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

        embedding = self._extract_embedding(audio_bytes, sample_rate)

        # Compare against all enrolled voiceprints
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
