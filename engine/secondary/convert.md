https://github.com/hiennguyen9874/deepstream-face-recognition/releases/download/v0.1/webface_r50_dynamic_simplify_cleanup.onnx

/usr/src/tensorrt/bin/trtexec --onnx=./webface_r50_dynamic_simplify_cleanup.onnx \
 --saveEngine=./webface_r50.engine \
 --minShapes=input.1:1x3x112x112 \
 --optShapes=input.1:4x3x112x112 \
 --maxShapes=input.1:4x3x112x112
