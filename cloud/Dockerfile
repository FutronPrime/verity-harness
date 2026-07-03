# VERITY Cloud — build from the REPO ROOT so app.py can import the verity modules:
#   docker build -f cloud/Dockerfile -t verity-cloud .
FROM python:3.12-slim
WORKDIR /app
COPY cloud/requirements.txt /app/cloud/requirements.txt
RUN pip install --no-cache-dir -r /app/cloud/requirements.txt || true
COPY . /app
ENV VERITY_CLOUD_PORT=8787 \
    VERITY_CLOUD_DB=/data/ledger.db
VOLUME ["/data"]
EXPOSE 8787
CMD ["python", "cloud/app.py"]
