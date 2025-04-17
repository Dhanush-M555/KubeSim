#!/usr/bin/env python
"""
Real application test for pod rescheduling after node deletion.
This test launches the actual application and tests if pod rescheduling works properly.
"""

import os
import time
import json
import sys
import subprocess
import requests
import signal
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

def test_pod_rescheduling():
    """
    Test that pods get properly rescheduled when a node is deleted.
    This test:
    1. Updates the config to enable auto-scaling
    2. Starts the application
    3. Creates multiple nodes
    4. Launches pods on a specific node
    5. Deletes that node
    6. Verifies that the pods were rescheduled to another node
    """
    # Step 1: Update config for testing
    config = {
        "AUTO_SCALE": True,
        "SCHEDULING_ALGO": "first-fit",
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
        
        # Step 3: Create nodes
        print("Creating nodes...")
        node1_response = requests.post(f"{api_url}/add-node", json={"cores": 4})
        if node1_response.status_code != 200:
            print(f"Failed to create first node: {node1_response.text}")
            return False
        
        node1_data = node1_response.json()
        node1_id = node1_data["node_id"]
        print(f"Created node: {node1_id}")
        
        node2_response = requests.post(f"{api_url}/add-node", json={"cores": 4})
        if node2_response.status_code != 200:
            print(f"Failed to create second node: {node2_response.text}")
            return False
        
        node2_data = node2_response.json()
        node2_id = node2_data["node_id"]
        print(f"Created node: {node2_id}")
        
        # Wait for nodes to initialize
        time.sleep(5)
        
        # Step 4: Launch pods on the first node
        print("Launching pods on the first node...")
        pod1_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "test_pod_1", "cpu": 2}
        )
        if pod1_response.status_code != 200:
            print(f"Failed to launch pod 1: {pod1_response.text}")
            return False
        
        pod2_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "test_pod_2", "cpu": 1}
        )
        if pod2_response.status_code != 200:
            print(f"Failed to launch pod 2: {pod2_response.text}")
            return False
        
        # Wait for pods to start
        time.sleep(5)
        
        # Get pod status to verify they're on the expected nodes
        pods_status_response = requests.get(f"{api_url}/pod-status")
        pods_status = pods_status_response.json()
        print("Initial pod status:", json.dumps(pods_status, indent=2))
        
        # Find which node has the pods
        pod1_node = None
        pod2_node = None
        for node_id, node_data in pods_status.items():
            if "test_pod_1" in node_data:
                pod1_node = node_id
            if "test_pod_2" in node_data:
                pod2_node = node_id
        
        # If both pods are on the same node, delete that node
        target_node = None
        if pod1_node == pod2_node:
            target_node = pod1_node
        else:
            # If they're on different nodes, pick the first node
            target_node = pod1_node
        
        print(f"Pods are on node(s): pod1={pod1_node}, pod2={pod2_node}")
        print(f"Will delete node: {target_node}")
        
        # Step 5: Delete the node with the pods
        print(f"Deleting node {target_node}...")
        delete_response = requests.delete(
            f"{api_url}/delete-node",
            json={"node_id": target_node}
        )
        
        if delete_response.status_code != 200:
            print(f"Failed to delete node: {delete_response.text}")
            return False
        
        delete_result = delete_response.json()
        print("Delete node response:", json.dumps(delete_result, indent=2))
        
        # Wait for rescheduling to complete
        time.sleep(10)
        
        # Step 6: Verify pods were rescheduled
        print("Checking if pods were rescheduled...")
        final_status_response = requests.get(f"{api_url}/pod-status")
        final_status = final_status_response.json()
        print("Final pod status:", json.dumps(final_status, indent=2))
        
        # Check if the pods exist on any node
        found_pod1 = False
        found_pod2 = False
        
        for node_id, node_data in final_status.items():
            if "test_pod_1" in node_data:
                found_pod1 = True
                print(f"Found pod1 on node {node_id}")
            if "test_pod_2" in node_data:
                found_pod2 = True
                print(f"Found pod2 on node {node_id}")
        
        # Make sure deleted node is gone
        assert target_node not in final_status, f"Deleted node {target_node} should not be in final status"
        
        # Check if pods were successfully rescheduled
        if "failed_reschedules" in delete_result:
            for failed_pod in delete_result["failed_reschedules"]:
                pod_id = failed_pod["pod_id"]
                if pod_id == "test_pod_1":
                    found_pod1 = False
                elif pod_id == "test_pod_2":
                    found_pod2 = False
        
        if found_pod1 and found_pod2:
            print("SUCCESS: All pods were successfully rescheduled!")
            return True
        else:
            missing_pods = []
            if not found_pod1:
                missing_pods.append("test_pod_1")
            if not found_pod2:
                missing_pods.append("test_pod_2")
            print(f"FAILURE: Some pods were not rescheduled: {', '.join(missing_pods)}")
            return False
        
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
    success = test_pod_rescheduling()
    
    # Exit with appropriate status code
    sys.exit(0 if success else 1) 