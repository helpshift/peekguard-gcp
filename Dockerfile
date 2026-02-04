FROM python:3.12.9-slim

# 1. Setup Environment
WORKDIR /app
# PYTHONUNBUFFERED ensures logs stream to Cloud Logging immediately
ENV PYTHONUNBUFFERED=1 \
    HSFT_CONF_ENV=sandbox

# 2. Install System Dependencies
# 'build-essential' is REQUIRED for posix_ipc compilation
# 'libgomp1' is REQUIRED for Spacy/Torch
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 3. Upgrade pip
RUN pip install --no-cache-dir --upgrade pip --root-user-action=ignore

# 4. Pre-install CPU-only Torch (Optimization)
# Prevents downloading the massive GPU version if presidio pulls it in
RUN pip install --no-cache-dir \
    torch==2.5.1+cpu torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cpu \
    --root-user-action=ignore

# 5. Install Project Dependencies
COPY pyproject.toml .
# This installs everything, including the Spacy model from the URL in toml
RUN pip install --no-cache-dir . --root-user-action=ignore

# 6. Copy Application Code
COPY . .

# 7. Runtime
EXPOSE 8080

# Run the module
CMD ["python", "-m", "peekguard.main"]
