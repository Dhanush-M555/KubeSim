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

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Python 3.9+
- Node.js/npm


### Running the Application

Run these in separate terminals

1.  **Start the Backend**:
    This script will start the main Flask API server and ensure the necessary Docker network is created.
    ```bash
    ./start.sh 
    ```

2.  **Start the Frontend**:
    Navigate to the `kubesim` directory and run the frontend start script:
    ```bash
    ./start-frontend.sh 
    ```

## Running Tests

There are two sets of tests available:

1.  **Mocked Tests**: These use `unittest` and mocks to test application logic without running the full system.
    ```bash
    python -m tests.run_tests
    ```

2.  **Real Application Tests**: These launch the actual backend and Docker containers to test real-world scenarios. **Ensure Docker is running and the node image is built (`./start.sh build`) before running these.**
    ```bash
    python -m tests.run_real_tests
    ```
    See `tests/README.md` for more details on the specific real tests.

## Features

- **Node Management**: Add/remove Docker containers as nodes
- **Pod Scheduling**: Schedule pods (threads) on nodes using configurable algorithms
- **Resource Monitoring**: Track CPU usage across nodes and pods
- **Health Checks**: Detect unhealthy nodes and pods
- **Auto-Scaling**: ⚠️ **Caution: The auto-scaling feature is still under construction. It is recommended not to use it until the upcoming update.**
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
- `DEFAULT_NODE_CAPACITY`: Default CPU cores per node.
- `AUTO_SCALE_HIGH_THRESHOLD`, `AUTO_SCALE_LOW_THRESHOLD`: Usage thresholds for auto-scaling.

## Reporting Issues

If you encounter any issues or bugs, please raise an issue.