FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

LABEL maintainer="Wyoming Voice Match"
LABEL description="Wyoming ASR proxy with ECAPA-TDNN speaker verification"

WORKDIR /app

# Install Python and system dependencies, remove unused CUDA packages from base
RUN apt-get update && \
    apt-get remove -y --autoremove \
        cuda-libraries-12-1 \
        libnpp-12-1 \
        libnccl2 2>/dev/null || true && \
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
    # Remove Triton compiler (~600MB, not needed for inference)
    pip uninstall -y triton 2>/dev/null; \
    # Remove PyTorch test/debug/static files
    find /usr/local/lib/python3.10/dist-packages/torch -name "*.a" -delete && \
    find /usr/local/lib/python3.10/dist-packages/torch -name "test" -type d -exec rm -rf {} + 2>/dev/null; \
    find /usr/local/lib/python3.10/dist-packages/torch -name "tests" -type d -exec rm -rf {} + 2>/dev/null; \
    # Remove unused CUDA libs bundled with PyTorch
    cd /usr/local/lib/python3.10/dist-packages/torch/lib && \
    rm -f libnccl* libcublas* libcublasLt* libcusparse* libcusolver* \
          libcufft* libcurand* libnvrtc* libnvJitLink* libnvfuser* && \
    # Remove torch.distributed (multi-node training, not needed)
    rm -rf /usr/local/lib/python3.10/dist-packages/torch/distributed && \
    rm -rf /usr/local/lib/python3.10/dist-packages/torch/_inductor && \
    rm -rf /usr/local/lib/python3.10/dist-packages/torch/_dynamo && \
    rm -rf /usr/local/lib/python3.10/dist-packages/torch/_functorch && \
    rm -rf /usr/local/lib/python3.10/dist-packages/torch/ao && \
    rm -rf /usr/local/lib/python3.10/dist-packages/torch/onnx && \
    # Remove SpeechBrain extras
    rm -rf /usr/local/lib/python3.10/dist-packages/speechbrain/recipes && \
    rm -rf /usr/local/lib/python3.10/dist-packages/speechbrain/tests && \
    # Remove numpy tests
    find /usr/local/lib/python3.10/dist-packages/numpy -name "tests" -type d -exec rm -rf {} + 2>/dev/null; \
    echo "Cleanup complete"

# Copy application code
COPY wyoming_voice_match/ wyoming_voice_match/
COPY scripts/ scripts/

# Create data directory structure
RUN mkdir -p /data/enrollment /data/voiceprints /data/models

EXPOSE 10350

ENTRYPOINT ["python", "-m", "wyoming_voice_match"]