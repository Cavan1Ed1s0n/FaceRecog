https://drive.google.com/file/d/1ROzukAntle8VheqNImffH4d_PD_Vrwn4/view?usp=sharing

/usr/src/tensorrt/bin/trtexec --onnx=./retinaface_mobilenet.onnx \
        --saveEngine=./retinaface_mobilenet_b4.engine \
        --minShapes=input:1x3x640x640 \
        --optShapes=input:4x3x640x640 \
        --maxShapes=input:4x3x640x640 \
        --verbose
