# KubeSim: Distributed Systems Cluster Simulation Framework

A Kubernetes-like cluster simulator with nodes (Docker containers), pods (threads), resource monitoring, scheduling, and auto-scaling capabilities.

## Project Overview

KubeSim simulates a Kubernetes-like cluster environment for educational purposes. It provides:

- Docker-based node management
- Thread-based pod scheduling
- CPU usage monitoring
- Auto-scaling based on resource usage
- Multiple scheduling algorithms (first-fit, best-fit, worst-fit)
- Web UI for monitoring and management

## Architecture

- **Backend**: Flask API Server (port 5000) + Docker containers (nodes)
- **Frontend**: React with shadcn UI components and Chart.js
- **Configuration**: Static `config.json` file (Kubernetes-style)

## Setup Instructions

### Prerequisites

- Docker
- Python 3.9+
- Node.js/npm

### Backend Setup

1. Install Python dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Create Docker network:
   ```
   docker network create cluster-net
   ```

3. Build the node image:
   ```
   docker build -t node_image .
   ```

4. Create data directory:
   ```
   sudo mkdir -p /var/cluster-data
   sudo chmod 777 /var/cluster-data
   ```

5. Start the Flask API server:
   ```
   python app.py
   ```

### Frontend Setup

1. Navigate to the React app directory:
   ```
   cd kubesim
   ```

2. Install dependencies:
   ```
   npm install
   ```

3. Start the development server:
   ```
   npm start
   ```

4. Access the UI at http://localhost:3000

## Features

- **Node Management**: Add/remove Docker containers as nodes
- **Pod Scheduling**: Schedule pods (threads) on nodes using configurable algorithms
- **Resource Monitoring**: Track CPU usage across nodes and pods
- **Health Checks**: Detect unhealthy nodes and pods
- **Auto-Scaling**: Automatically scale the cluster based on resource usage
- **Interactive UI**: Visualize cluster state, resource usage, and pod distribution

## API Endpoints

- `/add-node` (POST): Add a new node to the cluster
- `/launch-pod` (POST): Schedule a pod on a node
- `/pod-status` (GET): Get status of all pods
- `/heartbeat` (POST): Receive heartbeats from nodes
- `/list-nodes` (GET): List all nodes and their status

## Configuration

Edit `config.json` to configure:

- `AUTO_SCALE` (boolean): Enable/disable auto-scaling
- `SCHEDULING_ALGO` (string): Choose scheduling algorithm ("first-fit", "best-fit", "worst-fit")

## License

This project is for educational purposes only.