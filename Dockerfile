# Public demo image: FastAPI app + synthetic data. The Token Factory key is NOT in the image;
# it is passed as an environment variable at deploy time (deploy/cloudrun.sh).
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DEMO_PUBLIC=1 PORT=8080
WORKDIR /app
COPY requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt
COPY agent/ agent/
COPY app/ app/
COPY data/gen_synthetic.py data/gen_synthetic.py
COPY data/precomputed/ data/precomputed/
RUN python data/gen_synthetic.py
RUN useradd -u 10001 -m web && chown -R web /app
USER web
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
