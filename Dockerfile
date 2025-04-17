FROM python:3.9-slim

WORKDIR /app

COPY node_manager.py .
COPY config.json .

RUN apt-get update && apt-get install -y \
    iproute2 \
    iputils-ping \
    net-tools \
    && rm -rf /var/lib/apt/lists/* \
    && pip install psutil requests flask

# Create the data directory
RUN mkdir -p /data

# Copy config to the data directory as well (fallback)
COPY config.json /data/config.json

EXPOSE 5001

# Always use the mounted config if available, otherwise use local copy
CMD ["python", "node_manager.py"] 