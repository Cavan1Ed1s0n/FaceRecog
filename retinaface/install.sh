#!/usr/bin/env bash
set -e

log() {
    echo -e "$@"
}

# --- Detect CUDA version ---
cuda_version=$(nvcc --version | grep -oP 'V\K\d+\.\d+')
log "[INFO] CUDA Version: $cuda_version"
export CUDA_VER=$cuda_version

# --- Detect DeepStream version ---
DEEPSTREAM_DIR=$(ls -d /opt/nvidia/deepstream/deepstream-* 2>/dev/null || true)

if [[ $DEEPSTREAM_DIR =~ deepstream-([0-9]+\.[0-9]+) ]]; then
    DEEPSTREAM_VERSION="${BASH_REMATCH[1]}"
    log "[INFO] Detected DeepStream version: $DEEPSTREAM_VERSION"
else
    log "[WARN] Could not detect DeepStream version automatically. Using default 6.3"
    DEEPSTREAM_VERSION="6.3"
fi
export NVDS_VERSION=$DEEPSTREAM_VERSION

# --- Build custom parser ---
log "[INFO] Building nvdsinfer_customparser with CUDA_VER=$CUDA_VER and NVDS_VERSION=$NVDS_VERSION"
cd nvdsinfer_customparser
make CUDA_VER=$CUDA_VER NVDS_VERSION=$NVDS_VERSION

# --- Copy .so file into DeepStream lib ---
so_file=$(ls *.so | head -n 1 || true)

if [[ -n "$so_file" ]]; then
    cp "$so_file" "/opt/nvidia/deepstream/deepstream/lib/"
    log "[INFO] Copied $so_file to /opt/nvidia/deepstream/deepstream/lib/"
else
    log "[ERROR] No .so file found in nvdsinfer_customparser"
    exit 1
fi
