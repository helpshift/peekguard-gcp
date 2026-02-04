FROM python:3.12.9-slim

# 1. Setup Environment
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    HSFT_CONF_ENV=sandbox \
    WORKERS=3

# 2. Install System Dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 3. Upgrade pip (This suppresses the root warning in newer versions)
RUN pip install --no-cache-dir --upgrade pip --root-user-action=ignore

# 4. Install PyTorch (CPU Only)
RUN pip install --no-cache-dir \
    torch==2.5.1+cpu torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cpu \
    --root-user-action=ignore

# 5. Install Other Python Dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir . --root-user-action=ignore

# 6. Download Spacy Model
RUN python -m spacy download en_core_web_sm

# 7. Copy Application Code
COPY . .

# 8. Run
EXPOSE 8045
CMD ["python", "-m", "peekguard.main"]
