#!/usr/bin/env python
"""
Real application test for the Worst-Fit scheduling algorithm.
This test verifies that the Worst-Fit algorithm correctly places pods on the node that will have the most remaining capacity.
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

def test_worst_fit_algorithm():
    """
    Test that the Worst-Fit scheduling algorithm works correctly.
    
    Worst-Fit places pods on the node that will have the most remaining capacity after placement.
    
    This test:
    1. Updates config to use worst-fit algorithm
    2. Starts the application
    3. Creates nodes with different capacities
    4. Launches pods and verifies they go to the node with most remaining capacity
    5. Verifies the placement is correct according to worst-fit behavior
    """
    # Step 1: Update config for testing
    config = {
        "AUTO_SCALE": False,  # Disable auto-scaling
        "SCHEDULING_ALGO": "worst-fit",  # Set algorithm to worst-fit
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
        
        # Step 4: Create initial pod allocations to set up the test:
        # Node 1 (4 cores): Use 2 cores -> 2 cores remaining
        # Node 2 (6 cores): Use 3 cores -> 3 cores remaining
        # Node 3 (8 cores): Use 2 cores -> 6 cores remaining
        
        print("Setting up initial pod allocations...")
        
        # Pod 1 on Node 1 (2 cores)
        pod1_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "setup_pod_1", "cpu": 2}
        )
        if pod1_response.status_code != 200:
            print(f"Failed to launch setup pod 1: {pod1_response.text}")
            return False
        
        # Pod 2 on Node 2 (3 cores)
        pod2_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "setup_pod_2", "cpu": 3}
        )
        if pod2_response.status_code != 200:
            print(f"Failed to launch setup pod 2: {pod2_response.text}")
            return False
        
        # Pod 3 on Node 3 (2 cores)
        pod3_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "setup_pod_3", "cpu": 2}
        )
        if pod3_response.status_code != 200:
            print(f"Failed to launch setup pod 3: {pod3_response.text}")
            return False
        
        # Get status to see current allocations
        time.sleep(2)
        status_response = requests.get(f"{api_url}/pod-status")
        pod_status = status_response.json()
        print("\nInitial pod status:")
        for node_id, pods in pod_status.items():
            print(f"Node {node_id}:")
            for pod_id, pod_data in pods.items():
                print(f"  - {pod_id}: {pod_data}")
        
        # Print node allocations to debug the test
        nodes_response = requests.get(f"{api_url}/list-nodes")
        nodes_info = nodes_response.json()
        print("\nNode capacities:")
        for node in nodes_info:
            node_id = node["node_id"]
            capacity = node["capacity"]
            # Calculate used capacity from pods
            used = 0
            if node_id in pod_status:
                for pod_id, pod_data in pod_status[node_id].items():
                    used += pod_data.get("cpu_request", 0)
            available = capacity - used
            print(f"Node {node_id}: capacity={capacity}, used={used}, available={available}")
        
        # Step 5: Test the worst-fit algorithm with a 2-core pod
        # Get the actual node status first to confirm available capacity
        updated_nodes_response = requests.get(f"{api_url}/list-nodes") 
        updated_nodes_info = updated_nodes_response.json()
        print("\nUpdated node capacities before placing test pods:")
        node_capacities = {}
        for node in updated_nodes_info:
            node_id = node["node_id"]
            capacity = node["capacity"]
            # Calculate used capacity from pods
            used = 0
            if node_id in pod_status:
                for pod_id, pod_data in pod_status[node_id].items():
                    used += pod_data.get("cpu_request", 0)
            available = capacity - used
            node_capacities[node_id] = available
            print(f"Node {node_id}: capacity={capacity}, used={used}, available={available}")
            
        # Find node with most available capacity for worst-fit
        most_available_node = None
        most_available = -1
        for node_id, available in node_capacities.items():
            if available >= 2 and available > most_available:
                most_available = available
                most_available_node = node_id
        
        print(f"Node with most available capacity: {most_available_node} with {most_available} cores")
        
        print("\nTesting worst-fit with a 2-core pod...")
        test_pod1_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "test_pod_1", "cpu": 2}
        )
        if test_pod1_response.status_code != 200:
            print(f"Failed to launch test pod 1: {test_pod1_response.text}")
            return False
        
        # Check placement of test pod 1
        test_pod1_data = test_pod1_response.json()
        test_pod1_node = test_pod1_data.get("node_id")
        print(f"Test Pod 1 (2 cores) placed on node: {test_pod1_node}")
        
        # Worst-fit should have placed it on the node with most available capacity
        if test_pod1_node != most_available_node:
            print(f"ERROR: Worst-fit algorithm failed. Test Pod 1 should be on node {most_available_node} but is on {test_pod1_node}")
            return False
        
        # Step 6: Test with a 1-core pod
        # Get the actual node status first to confirm available capacity
        pod_status_response = requests.get(f"{api_url}/pod-status")
        updated_pod_status = pod_status_response.json()
        
        updated_nodes_response = requests.get(f"{api_url}/list-nodes") 
        updated_nodes_info = updated_nodes_response.json()
        print("\nUpdated node capacities after first pod placement:")
        node_capacities = {}
        for node in updated_nodes_info:
            node_id = node["node_id"]
            capacity = node["capacity"]
            # Calculate used capacity from pods
            used = 0
            if node_id in updated_pod_status:
                for pod_id, pod_data in updated_pod_status[node_id].items():
                    used += pod_data.get("cpu_request", 0)
            available = capacity - used
            node_capacities[node_id] = available
            print(f"Node {node_id}: capacity={capacity}, used={used}, available={available}")
            
        # Find node with most available capacity for worst-fit
        most_available_node = None
        most_available = -1
        for node_id, available in node_capacities.items():
            if available >= 1 and available > most_available:
                most_available = available
                most_available_node = node_id
        
        print(f"Node with most available capacity: {most_available_node} with {most_available} cores")
        
        print("\nTesting worst-fit with a 1-core pod...")
        test_pod2_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "test_pod_2", "cpu": 1}
        )
        if test_pod2_response.status_code != 200:
            print(f"Failed to launch test pod 2: {test_pod2_response.text}")
            return False
        
        # Check placement of test pod 2
        test_pod2_data = test_pod2_response.json()
        test_pod2_node = test_pod2_data.get("node_id")
        print(f"Test Pod 2 (1 core) placed on node: {test_pod2_node}")
        
        # Worst-fit should have placed it on the node with most available capacity
        if test_pod2_node != most_available_node:
            print(f"ERROR: Worst-fit algorithm failed. Test Pod 2 should be on node {most_available_node} but is on {test_pod2_node}")
            return False

        # Step 7: Fill the node with most capacity to test fail-over to second best
        # Get current node with most capacity and fill it
        pod_status_response = requests.get(f"{api_url}/pod-status")
        updated_pod_status = pod_status_response.json()
        
        updated_nodes_response = requests.get(f"{api_url}/list-nodes") 
        updated_nodes_info = updated_nodes_response.json()
        print("\nUpdated node capacities after second pod placement:")
        node_capacities = {}
        for node in updated_nodes_info:
            node_id = node["node_id"]
            capacity = node["capacity"]
            # Calculate used capacity from pods
            used = 0
            if node_id in updated_pod_status:
                for pod_id, pod_data in updated_pod_status[node_id].items():
                    used += pod_data.get("cpu_request", 0)
            available = capacity - used
            node_capacities[node_id] = available
            print(f"Node {node_id}: capacity={capacity}, used={used}, available={available}")
            
        # Find node with most available capacity to fill
        node_to_fill = most_available_node
        cores_to_request = node_capacities[node_to_fill]
        
        print(f"\nFilling node {node_to_fill} with {cores_to_request} cores...")
        fill_pod_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "setup_pod_4", "cpu": cores_to_request}
        )
        if fill_pod_response.status_code != 200:
            print(f"Failed to launch fill pod: {fill_pod_response.text}")
            return False
            
        # Step 8: Test with another 1-core pod after filling the best node
        # Get the actual node status first to confirm available capacity
        pod_status_response = requests.get(f"{api_url}/pod-status")
        updated_pod_status = pod_status_response.json()
        
        updated_nodes_response = requests.get(f"{api_url}/list-nodes") 
        updated_nodes_info = updated_nodes_response.json()
        print("\nUpdated node capacities after filling a node:")
        node_capacities = {}
        for node in updated_nodes_info:
            node_id = node["node_id"]
            capacity = node["capacity"]
            # Calculate used capacity from pods
            used = 0
            if node_id in updated_pod_status:
                for pod_id, pod_data in updated_pod_status[node_id].items():
                    used += pod_data.get("cpu_request", 0)
            available = capacity - used
            node_capacities[node_id] = available
            print(f"Node {node_id}: capacity={capacity}, used={used}, available={available}")
            
        # Find node with most available capacity for worst-fit
        most_available_node = None
        most_available = -1
        for node_id, available in node_capacities.items():
            if available >= 1 and available > most_available:
                most_available = available
                most_available_node = node_id
        
        print(f"Node with most available capacity: {most_available_node} with {most_available} cores")
        
        print("\nTesting worst-fit with another 1-core pod after node filling...")
        test_pod3_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "test_pod_3", "cpu": 1}
        )
        if test_pod3_response.status_code != 200:
            print(f"Failed to launch test pod 3: {test_pod3_response.text}")
            return False
        
        # Check placement of test pod 3
        test_pod3_data = test_pod3_response.json()
        test_pod3_node = test_pod3_data.get("node_id")
        print(f"Test Pod 3 (1 core) placed on node: {test_pod3_node}")
        
        # Worst-fit should have placed it on the node with most available capacity
        if test_pod3_node != most_available_node:
            print(f"ERROR: Worst-fit algorithm failed. Test Pod 3 should be on node {most_available_node} but is on {test_pod3_node}")
            return False
        
        # Get final status and display for verification
        final_status_response = requests.get(f"{api_url}/pod-status")
        final_pod_status = final_status_response.json()
        print("\nFinal pod status:")
        for node_id, pods in final_pod_status.items():
            print(f"Node {node_id}:")
            for pod_id, pod_data in pods.items():
                print(f"  - {pod_id}: {pod_data}")
        
        print("\nSUCCESS: Worst-fit scheduling algorithm works correctly!")
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
    success = test_worst_fit_algorithm()
    
    # Exit with appropriate status code
    sys.exit(0 if success else 1) 