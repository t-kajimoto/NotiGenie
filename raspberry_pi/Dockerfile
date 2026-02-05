FROM debian:bookworm-slim

WORKDIR /app

# 1. Install System Python and Libraries (pre-compiled)
# Avoids compilation issues with PyAudio, Numpy, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    python3-pyaudio \
    python3-numpy \
    python3-scipy \
    python3-requests \
    python3-dotenv \
    libasound2 \
    portaudio19-dev \
    alsa-utils \
    usbutils \
    gcc \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# 2. Install remaining Pip packages (Google Cloud, Porcupine)
# Use --break-system-packages as we are in a container
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# 3. Add armhf architecture and Install 32-bit runtime (for AquesTalk Pi)
RUN dpkg --add-architecture armhf && \
    apt-get update && apt-get install -y --no-install-recommends \
    libc6:armhf \
    libstdc++6:armhf \
    libgcc-s1:armhf \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY . .

CMD ["python3", "app.py"]
