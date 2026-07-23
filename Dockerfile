FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# curl is only for the container healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Local container deployments can mount /data for the private cellar. The public
# Cloudflare release is generated separately as a read-only static catalog.
ENV WINEVALUE_CELLAR_DB=/data/cellar.db
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD curl -fsS http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "dashboard.py", \
     "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
