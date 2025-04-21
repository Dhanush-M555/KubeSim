#!/usr/bin/env python
"""
Real application test for the First-Fit scheduling algorithm.
This test verifies that the First-Fit algorithm correctly places pods on the first node with sufficient capacity.
"""

import os
import time
import json
import sys
import subprocess
import requests
import docker

def cleanup_containers():
    """Clean up all Docker containers created during testing"""
    print("Cleaning up containers...")
    client = docker.from_env()
    
    try:
        # Remove all containers in the cluster-net network
        containers = client.containers.list(all=True)
        for container in containers:
            try:
                if "node_" in container.name:
                    print(f"Stopping and removing container: {container.name}")
                    container.stop()
                    container.remove()
            except Exception as e:
                print(f"Error removing container {container.name}: {e}")
    except Exception as e:
        print(f"Error during cleanup: {e}")
    
    # Try to remove the network
    try:
        networks = client.networks.list(names=["cluster-net"])
        for network in networks:
            try:
                print(f"Removing network: {network.name}")
                network.remove()
            except Exception as e:
                print(f"Error removing network {network.name}: {e}")
    except Exception as e:
        print(f"Error listing networks: {e}")

def wait_for_api(base_url, max_attempts=20, delay=1):
    """Wait for the API to become available"""
    print(f"Waiting for API at {base_url}...")
    for i in range(max_attempts):
        try:
            response = requests.get(f"{base_url}/list-nodes", timeout=2)
            if response.status_code == 200:
                print("API is ready!")
                return True
        except requests.exceptions.RequestException:
            pass
        
        time.sleep(delay)
        
    print("API did not become available in time")
    return False

def test_first_fit_algorithm():
    """
    Test that the First-Fit scheduling algorithm works correctly.
    
    First-Fit places pods on the first node with sufficient capacity.
    
    This test:
    1. Updates config to use first-fit algorithm
    2. Starts the application
    3. Creates nodes with different capacities and usage
    4. Launches pods to verify they go to the first suitable node
    5. Verifies the placement is correct according to first-fit behavior
    """
    # Step 1: Update config for testing
    config = {
        "AUTO_SCALE": False,  # Disable auto-scaling
        "SCHEDULING_ALGO": "first-fit",  # Set algorithm to first-fit
        "DEFAULT_NODE_CAPACITY": 4,
        "AUTO_SCALE_HIGH_THRESHOLD": 80,
        "AUTO_SCALE_LOW_THRESHOLD": 20,
        "HEAVENLY_RESTRICTION": False
    }
    
    with open("config.json", "w") as f:
        json.dump(config, f, indent=2)
    
    # Step 2: Start the application
    api_url = "http://localhost:5000"
    
    # Clean up any existing containers
    cleanup_containers()
    
    # Start the application as a subprocess
    print("Starting KubeSim application...")
    app_process = subprocess.Popen(["python", "app.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    try:
        # Wait for API to be ready
        if not wait_for_api(api_url, max_attempts=20):
            print("API did not start properly, aborting test")
            app_process.terminate()
            return False
        
        # Step 3: Create nodes with different capacities
        print("Creating nodes...")
        
        # Node 1 with 4 cores
        node1_response = requests.post(f"{api_url}/add-node", json={"cores": 4})
        if node1_response.status_code != 200:
            print(f"Failed to create node 1: {node1_response.text}")
            return False
        
        node1_data = node1_response.json()
        node1_id = node1_data["node_id"]
        print(f"Created node 1: {node1_id} with 4 cores")
        
        # Node 2 with 6 cores
        node2_response = requests.post(f"{api_url}/add-node", json={"cores": 6})
        if node2_response.status_code != 200:
            print(f"Failed to create node 2: {node2_response.text}")
            return False
        
        node2_data = node2_response.json()
        node2_id = node2_data["node_id"]
        print(f"Created node 2: {node2_id} with 6 cores")
        
        # Node 3 with 8 cores
        node3_response = requests.post(f"{api_url}/add-node", json={"cores": 8})
        if node3_response.status_code != 200:
            print(f"Failed to create node 3: {node3_response.text}")
            return False
        
        node3_data = node3_response.json()
        node3_id = node3_data["node_id"]
        print(f"Created node 3: {node3_id} with 8 cores")
        
        # Wait for nodes to initialize
        time.sleep(5)
        
        # Step 4: Fill node 1 with pods to leave only 1 core available
        print("Filling node 1 with pods...")
        pod1_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "pod_1", "cpu": 3}
        )
        if pod1_response.status_code != 200:
            print(f"Failed to launch pod 1: {pod1_response.text}")
            return False
        
        # Check placement of pod 1
        pod1_node = pod1_response.json().get("node_id")
        print(f"Pod 1 placed on node: {pod1_node}")
        
        # First-fit should have placed it on the first node (node 1)
        if pod1_node != node1_id:
            print(f"ERROR: First-fit algorithm failed. Pod 1 should be on node {node1_id} but is on {pod1_node}")
            return False
        
        # Step 5: Launch another pod requiring 2 cores
        # This should skip node 1 (only 1 core left) and go to node 2
        print("Launching pod 2 needing 2 cores...")
        pod2_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "pod_2", "cpu": 2}
        )
        if pod2_response.status_code != 200:
            print(f"Failed to launch pod 2: {pod2_response.text}")
            return False
        
        # Check placement of pod 2
        pod2_node = pod2_response.json().get("node_id")
        print(f"Pod 2 placed on node: {pod2_node}")
        
        # First-fit should have placed it on node 2 (since node 1 doesn't have enough capacity)
        if pod2_node != node2_id:
            print(f"ERROR: First-fit algorithm failed. Pod 2 should be on node {node2_id} but is on {pod2_node}")
            return False
        
        # Step 6: Fill node 2 to leave only 1 core
        print("Filling node 2 with another pod...")
        pod3_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "pod_3", "cpu": 3}
        )
        if pod3_response.status_code != 200:
            print(f"Failed to launch pod 3: {pod3_response.text}")
            return False
        
        # Step 7: Launch a pod requiring 3 cores
        # This should skip node 1 & 2 (only 1 core left on each) and go to node 3
        print("Launching pod 4 needing 3 cores...")
        pod4_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "pod_4", "cpu": 3}
        )
        if pod4_response.status_code != 200:
            print(f"Failed to launch pod 4: {pod4_response.text}")
            return False
        
        # Check placement of pod 4
        pod4_node = pod4_response.json().get("node_id")
        print(f"Pod 4 placed on node: {pod4_node}")
        
        # First-fit should have placed it on node 3
        if pod4_node != node3_id:
            print(f"ERROR: First-fit algorithm failed. Pod 4 should be on node {node3_id} but is on {pod4_node}")
            return False
        
        # Get final status and display for verification
        status_response = requests.get(f"{api_url}/pod-status")
        pod_status = status_response.json()
        print("\nFinal pod status:")
        for node_id, pods in pod_status.items():
            print(f"Node {node_id}:")
            for pod_id, pod_data in pods.items():
                print(f"  - {pod_id}: {pod_data}")
        
        print("\nSUCCESS: First-fit scheduling algorithm works correctly!")
        return True
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        return False
    finally:
        # Clean up
        print("Stopping application...")
        app_process.terminate()
        app_process.wait(timeout=5)
        cleanup_containers()

if __name__ == "__main__":
    # Run the test
    success = test_first_fit_algorithm()
    
    # Exit with appropriate status code
    sys.exit(0 if success else 1) 