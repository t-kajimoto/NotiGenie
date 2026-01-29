FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
# portaudio19-dev is required for PyAudio
# libasound2-dev is required for sounddevice
RUN apt-get update && apt-get install -y \
    gcc \
    portaudio19-dev \
    libasound2-dev \
    libopenjp2-7 \
    fonts-noto-cjk \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Waveshare e-Paper library
RUN git clone https://github.com/waveshare/e-Paper.git /tmp/e-Paper \
    && cd /tmp/e-Paper/RaspberryPi_JetsonNano/python/ \
    && python setup.py install \
    && rm -rf /tmp/e-Paper

COPY . .

CMD ["python", "app.py"]
