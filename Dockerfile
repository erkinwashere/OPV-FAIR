FROM python:3.11-slim

# System deps (lxml, HDF5, build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-lxml \
    libhdf5-dev \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install package in editable mode
COPY . .
RUN pip install --no-cache-dir -e ".[dev]"

# Default: run the pipeline
CMD ["python", "run_pipeline.py", "--data", "data/raw", "--out", "data/fair"]
