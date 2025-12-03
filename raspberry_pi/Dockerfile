FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
# portaudio19-dev is required for PyAudio
# libasound2-dev is required for sounddevice
RUN apt-get update && apt-get install -y \
    gcc \
    portaudio19-dev \
    libasound2-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "app.py"]
