FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    CANOPY_BIND_HOST=0.0.0.0 CANOPY_DB_PATH=/data/canopy.sqlite3
WORKDIR /app
COPY requirements.txt requirements.lock ./
RUN python -m pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements.lock \
    && useradd --system --uid 10001 --home /app canopy \
    && mkdir /data \
    && chown canopy:canopy /data
COPY --chown=canopy:canopy canopy_app/ ./canopy_app/
COPY --chown=canopy:canopy canopy.py manage.py evaluate.py ./
USER canopy
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/livez', timeout=2)"
CMD ["python", "canopy.py"]
