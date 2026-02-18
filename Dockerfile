FROM python:3.12.9-slim AS builder

WORKDIR /app
ENV PYTHONUNBUFFERED=1

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 1. CREATE THE DIRECTORY
RUN mkdir -p /root/.pip

# 2. COPY THE SECRET FILE
# This file comes from the Cloud Build step above
COPY pip.conf /root/.pip/pip.conf

# 3. Install Dependencies
# pip will automatically read /root/.pip/pip.conf and find 'hspymonitoring'
COPY pyproject.toml .
RUN pip install --no-cache-dir . --root-user-action=ignore

# ==========================================
# STAGE 2: Runtime
# ==========================================
FROM python:3.12.9-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    HSFT_CONF_ENV=sandbox \
    PORT=8045 \
    PYTHON=python3

# Install minimal runtime libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 4. COPY INSTALLED LIBRARIES ONLY
# We copy the libraries from the builder, but NOT the /root/.pip/pip.conf file!
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy App Code
COPY . .

EXPOSE 8045
CMD ["python", "-m", "peekguard.main"]