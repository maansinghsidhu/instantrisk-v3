# InstantRisk Backend Dockerfile - LEAN
# No Python packages installed in image - all packages live on EFS at /mnt/efs/site-packages
# Image is just Python runtime + system dependencies (~200MB)

FROM public.ecr.aws/docker/library/python:3.12-slim

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# System dependencies only (WeasyPrint PDF, ffmpeg voice, tesseract OCR, curl healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    tesseract-ocr \
    libmagic1 \
    libgobject-2.0-0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libcairo2 \
    libffi8 \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Create dirs
RUN mkdir -p /home/appuser/.config/matplotlib /mnt/efs \
    && chown -R appuser:appuser /home/appuser

# Copy application code only
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser alembic/ ./alembic/
COPY --chown=appuser:appuser alembic.ini ./

# All Python packages are on EFS at /mnt/efs/site-packages (mounted at runtime)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    MPLCONFIGDIR=/home/appuser/.config/matplotlib \
    PYTHONPATH=/mnt/efs/site-packages

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=300s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health/live || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
