FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

LABEL maintainer="Wyoming Voice Match"
LABEL description="Wyoming ASR proxy with ECAPA-TDNN speaker verification"

WORKDIR /app

# Install Python and system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        libsndfile1 \
        ffmpeg && \
    ln -sf /usr/bin/python3 /usr/bin/python && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install PyTorch (CUDA 12.1) with minimal footprint, then app dependencies
# Then strip unnecessary files to reduce image size
COPY requirements.txt .
RUN pip install --no-cache-dir \
        torch torchaudio --index-url https://download.pytorch.org/whl/cu121 && \
    pip install --no-cache-dir -r requirements.txt && \
    # Remove PyTorch test/debug files
    find /usr/local/lib/python3.10/dist-packages/torch -name "*.a" -delete && \
    find /usr/local/lib/python3.10/dist-packages/torch -name "test" -type d -exec rm -rf {} + 2>/dev/null; \
    find /usr/local/lib/python3.10/dist-packages/torch -name "tests" -type d -exec rm -rf {} + 2>/dev/null; \
    # Remove unused CUDA libs bundled with PyTorch (we only need core + cuDNN)
    rm -rf /usr/local/lib/python3.10/dist-packages/torch/lib/libnccl* && \
    rm -rf /usr/local/lib/python3.10/dist-packages/torch/lib/libcublas* && \
    rm -rf /usr/local/lib/python3.10/dist-packages/torch/lib/libcusparse* && \
    rm -rf /usr/local/lib/python3.10/dist-packages/torch/lib/libcusolver* && \
    rm -rf /usr/local/lib/python3.10/dist-packages/torch/lib/libcufft* && \
    rm -rf /usr/local/lib/python3.10/dist-packages/torch/lib/libcurand* && \
    rm -rf /usr/local/lib/python3.10/dist-packages/torch/lib/libnvrtc* && \
    rm -rf /usr/local/lib/python3.10/dist-packages/torch/lib/libnvJitLink* && \
    # Remove triton (not needed for inference)
    rm -rf /usr/local/lib/python3.10/dist-packages/triton && \
    # Remove numpy tests
    find /usr/local/lib/python3.10/dist-packages/numpy -name "tests" -type d -exec rm -rf {} + 2>/dev/null; \
    # Remove SpeechBrain tests and recipes
    rm -rf /usr/local/lib/python3.10/dist-packages/speechbrain/recipes && \
    rm -rf /usr/local/lib/python3.10/dist-packages/speechbrain/tests && \
    echo "Cleanup complete"

# Copy application code
COPY wyoming_voice_match/ wyoming_voice_match/
COPY scripts/ scripts/

# Create data directory structure
RUN mkdir -p /data/enrollment /data/voiceprints /data/models

EXPOSE 10350

ENTRYPOINT ["python", "-m", "wyoming_voice_match"]