#!/bin/bash
set -e

echo "=== Preparing Primary Engine ==="
cd /app/engine/primary
if [ ! -f retinaface_mobilenet_b4.engine ]; then
    pip install --no-cache-dir gdown
    gdown "https://drive.google.com/uc?id=1ROzukAntle8VheqNImffH4d_PD_Vrwn4" -O retinaface_mobilenet.onnx
    /usr/src/tensorrt/bin/trtexec \
        --onnx=./retinaface_mobilenet.onnx \
        --saveEngine=./retinaface_mobilenet_b4.engine \
        --minShapes=input:1x3x640x640 \
        --optShapes=input:4x3x640x640 \
        --maxShapes=input:4x3x640x640 \
        --verbose
else
    echo "Primary engine already exists, skipping..."
fi

echo "=== Preparing Secondary Engine ==="
cd /app/engine/secondary
if [ ! -f webface_r50.engine ]; then
    wget -O webface_r50_dynamic_simplify_cleanup.onnx \
        https://github.com/hiennguyen9874/deepstream-face-recognition/releases/download/v0.1/webface_r50_dynamic_simplify_cleanup.onnx
    /usr/src/tensorrt/bin/trtexec \
        --onnx=./webface_r50_dynamic_simplify_cleanup.onnx \
        --saveEngine=./webface_r50.engine \
        --minShapes=input.1:1x3x112x112 \
        --optShapes=input.1:4x3x112x112 \
        --maxShapes=input.1:4x3x112x112

else
    echo "Secondary engine already exists, skipping..."
fi

echo "=== Starting FastAPI App ==="
cd /app
exec uvicorn main:app --host 0.0.0.0 --port 8090 --reload
