# Stage 1: builder — install all dependencies (including dev) for compilation
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.11.4 /uv /usr/local/bin/uv

# Install all deps (including dev) so build-time tools are available
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen

# Copy source so the builder stage has a complete tree if needed by build steps
COPY . .

# Stage 2: runtime — lean image with only what's needed to run
FROM python:3.12-slim AS runtime

# System deps for MediaPipe, OpenCV (headless), WeasyPrint
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libfontconfig1 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libcairo2 \
    fonts-liberation \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.11.4 /uv /usr/local/bin/uv

# Copy the virtualenv built in the builder stage (no dev deps at runtime)
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

# Copy application source only (no tests, no scripts — excluded via .dockerignore)
COPY app/ ./app/

# Download MediaPipe BlazePose Heavy task model. The Linux x86_64 wheel
# for mediapipe 0.10.x does NOT ship the legacy ``solutions`` API, so
# pose extraction uses the Tasks API which requires this .task file.
# See app/cv/pose_extraction.py and the related PR for context.
RUN mkdir -p /app/models && \
    curl -fsSL \
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task" \
        -o /app/models/pose_landmarker_heavy.task

# Create temp dir for video processing
RUN mkdir -p /tmp/spelix

# Run as non-root user for security
RUN useradd -m -r spelix && chown spelix:spelix /tmp/spelix
USER spelix

EXPOSE 8000

CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
