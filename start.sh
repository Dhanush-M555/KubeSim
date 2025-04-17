#!/bin/bash

echo "Starting KubeSim initialization..."

# Check Docker is running
if ! docker info > /dev/null 2>&1; then
  echo "Error: Docker is not running or not accessible. Please start Docker and try again."
  exit 1
fi

# Create Docker network
echo "Creating Docker network 'cluster-net'..."
docker network inspect cluster-net > /dev/null 2>&1 || docker network create cluster-net

# Build the Docker image
echo "Building 'node_image' for KubeSim nodes..."
docker build -t node_image .

# Create data directory
echo "Creating data directory for socket communication..."
sudo mkdir -p /var/cluster-data
echo "Copying config.json to shared location..."
sudo cp config.json /var/cluster-data/
echo "Setting permissions on shared directory..."
sudo chmod 777 /var/cluster-data

# Activate virtual environment if it exists, otherwise install requirements
if [ -d "venv" ]; then
  echo "Activating virtual environment..."
  source venv/bin/activate
else
  echo "Creating virtual environment and installing dependencies..."
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
fi

echo "Done!"
echo "Starting Flask API server on port 5000..."
python app.py 