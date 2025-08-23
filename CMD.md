docker-compose -f docker-compose.yml up -d
docker-compose up -d
docker-compose down
uvicorn main:app --host 0.0.0.0 --port 8090 --reload


docker image prune -f

docker builder prune -f

docker-compose up -d
docker-compose down
docker rmi -f 6d5e

lsof -i :8090  #check opening process at port 30000
sudo kill -9 <PID>
lsof -ti :8090 | xargs kill -9


docker build --no-cache --progress=plain -t qvision-ai-face-test-service:0.0.2 .



WORKDIR /engine/primary
# Download from Google Drive via gdown (easiest way inside Docker)
RUN pip install gdown && \
    gdown "https://drive.google.com/uc?id=1ROzukAntle8VheqNImffH4d_PD_Vrwn4" -O retinaface_mobilenet.onnx && \
    /usr/src/tensorrt/bin/trtexec \
        --onnx=./retinaface_mobilenet.onnx \
        --saveEngine=./retinaface_mobilenet_b4.engine \
        --minShapes=input:1x3x640x640 \
        --optShapes=input:4x3x640x640 \
        --maxShapes=input:4x3x640x640 \
        --verbose

# ---- Build secondary (retinaface detector) ----
WORKDIR /engine/secondary

RUN wget -O webface_r50_dynamic_simplify_cleanup.onnx \
    https://github.com/hiennguyen9874/deepstream-face-recognition/releases/download/v0.1/webface_r50_dynamic_simplify_cleanup.onnx && \
    /usr/src/tensorrt/bin/trtexec \
        --onnx=./webface_r50_dynamic_simplify_cleanup.onnx \
        --saveEngine=./webface_r50.engine \
        --minShapes=input.1:1x3x112x112 \
        --optShapes=input.1:4x3x112x112 \
        --maxShapes=input.1:4x3x112x112
