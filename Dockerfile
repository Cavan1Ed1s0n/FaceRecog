FROM nvcr.io/nvidia/deepstream:6.3-triton-multiarch

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 \
        python3-dev \
        python3-pip \
        python3-numpy \
        python3-opencv \
        python3-gi \
        python3-gst-1.0 \
        libopencv-dev \
        libgstreamer1.0-dev \
        libgstreamer-plugins-base1.0-dev \
        libglib2.0-dev \
        libglib2.0-dev-bin \
        libgirepository1.0-dev \
        gobject-introspection \
        gir1.2-gst-rtsp-server-1.0 \
        libgstrtspserver-1.0-0 \
        gstreamer1.0-rtsp \
        ffmpeg \
        git \
        cmake \
        g++ \
        build-essential \
        libtool \
        m4 \
        autoconf \
        automake && \
    rm -rf /var/lib/apt/lists/*

RUN TARGETARCH=$(uname -m) && \
    echo "Building for: $TARGETARCH" && \
    WHEEL="pyds-1.1.8-py3-none-linux_${TARGETARCH}.whl" && \
    echo "Downloading $WHEEL" && \
    wget -O "$WHEEL" "https://github.com/NVIDIA-AI-IOT/deepstream_python_apps/releases/download/v1.1.8/$WHEEL" && \
    pip3 install "$WHEEL"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN cd /opt/nvidia/deepstream/deepstream && \
    ./user_additional_install.sh && \
    ./install.sh

# Install gst-nvinfer-custom
COPY gst-nvinfer-custom /app/gst-nvinfer-custom
RUN cd /app/gst-nvinfer-custom && \
    chmod +x install.sh && \
    ./install.sh || { echo "gst-nvinfer-custom install.sh failed"; exit 1; }

# Install retinaface
COPY retinaface /app/retinaface
RUN cd /app/retinaface && \
    chmod +x install.sh && \
    ./install.sh || { echo "retinaface install.sh failed"; exit 1; }
