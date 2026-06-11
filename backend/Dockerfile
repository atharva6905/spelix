# Stage 1: builder — install all dependencies (including dev) for compilation
FROM python:3.12-slim@sha256:804ddf3251a60bbf9c92e73b7566c40428d54d0e79d3428194edf40da6521286 AS builder

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.11.4 /uv /usr/local/bin/uv

# Install all deps (including dev) so build-time tools are available
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen

# Copy source so the builder stage has a complete tree if needed by build steps
COPY . .

# Stage 2: runtime — lean image with only what's needed to run
FROM python:3.12-slim@sha256:804ddf3251a60bbf9c92e73b7566c40428d54d0e79d3428194edf40da6521286 AS runtime

# System deps:
#   - libgl1: OpenCV headless rendering
#   - libgles2 + libegl1: MediaPipe Tasks API native deps (libmediapipe.so
#     links against libGLESv2.so.2 and libEGL.so.1 — verified via `ldd`)
#   - libglib2.0-0, libsm6, libxext6, libxrender1: OpenCV / fontconfig
#     transitive deps
#   - libfontconfig1, libpango-1.0-0, libpangocairo-1.0-0,
#     libgdk-pixbuf-2.0-0, libcairo2, fonts-liberation: WeasyPrint PDF
#     rendering
#   - ffmpeg: provides ``ffprobe``, used by
#     ``app/cv/quality_gates.py::_check_video_file`` to read video
#     duration. Without ffprobe the gate raises FileNotFoundError and
#     returns "Video file appears corrupt or unsupported" — which made
#     the entire pipeline silently fail at quality_gate_rejected even
#     for perfectly valid videos.
#   - curl: used at build time to download the BlazePose model file
#     and at runtime for the healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libgles2 \
    libegl1 \
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
    ffmpeg \
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
        -o /app/models/pose_landmarker_heavy.task && \
    echo "64437af838a65d18e5ba7a0d39b465540069bc8aae8308de3e318aad31fcbc7b  /app/models/pose_landmarker_heavy.task" | sha256sum -c -

# Pre-bake Docling model artifacts (layout + tableformer + RapidOCR) into the
# image at build time. The prod container runs non-root with a read-only venv;
# without this, Docling's RapidOCR backend tries to download its OCR model into
# the venv site-packages at first use and raises PermissionError, which made
# EVERY ingest_paper task fail (all rag_documents ended with chunk_count=0).
# See issue #263. DOCLING_ARTIFACTS_PATH points app/services/pdf_extraction.py
# at this writable, pre-populated dir so no runtime download is ever attempted.
ENV DOCLING_ARTIFACTS_PATH=/app/models/docling
RUN mkdir -p /app/models/docling && \
    uv run --no-dev docling-tools models download \
        layout tableformer rapidocr \
        -o /app/models/docling

# Create temp dir for video processing
RUN mkdir -p /tmp/spelix

# Run as non-root user for security
RUN useradd -m -r spelix && \
    chown -R spelix:spelix /tmp/spelix /app/models/docling
USER spelix

EXPOSE 8000

CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
