# ===============================
#       STAGE 1 — Builder
# ===============================

# CHANGE 1: Switched from nvidia/cuda to standard ubuntu:22.04
FROM ubuntu:22.04 AS builder

# Avoid tzdata interactive prompt
ENV DEBIAN_FRONTEND=noninteractive

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    curl \
    libffi-dev \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    liblzma-dev \
    tk-dev \
    uuid-dev \
    ca-certificates \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/python-build

# -----------------------
# Install Python 3.12.9
# -----------------------
RUN wget https://www.python.org/ftp/python/3.12.9/Python-3.12.9.tgz && \
    tar -xzf Python-3.12.9.tgz && \
    cd Python-3.12.9 && \
    ./configure --enable-optimizations --with-lto && \
    make -j"$(nproc)" && \
    make altinstall

# Make python3.12 default
RUN ln -sf /usr/local/bin/python3.12 /usr/bin/python && \
    ln -sf /usr/local/bin/pip3.12 /usr/bin/pip

# -----------------------
# Install Python packages
# -----------------------
WORKDIR /app

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# CHANGE 2: Install PyTorch CPU-only versions
# Uses the cpu index URL to avoid downloading massive CUDA binaries
RUN pip install --no-cache-dir \
    torch==2.5.1+cpu torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cpu

# Add pip config (optional)
COPY pip.conf /root/.pip/pip.conf

# Install your app deps
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Download spaCy Model
RUN python -m spacy download en_core_web_sm


# ===============================
#       STAGE 2 — Runtime
# ===============================
# CHANGE 3: Switched runtime base to standard ubuntu:22.04
FROM ubuntu:22.04 AS runtime

# Runtime working directory
WORKDIR /app

# Environment variables (runtime)
ENV PYTHONUNBUFFERED=1 \
    HSFT_CONF_ENV=sandbox \
    WORKERS=3

# Copy Python from builder
COPY --from=builder /usr/local /usr/local
COPY --from=builder /usr/bin/python /usr/bin/python
COPY --from=builder /usr/bin/pip /usr/bin/pip

# Copy pip config (optional)
COPY --from=builder /root/.pip /root/.pip

# Copy your FastAPI / app source
COPY . .

# Expose API port
EXPOSE 8045

# Run FastAPI server
CMD ["python", "-m", "peekguard.main"]