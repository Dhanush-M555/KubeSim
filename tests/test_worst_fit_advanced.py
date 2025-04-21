#!/usr/bin/env python
"""
Advanced real application test for the Worst-Fit scheduling algorithm.
Tests node deletion with multiple pods and verifies they get rescheduled correctly.
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

def test_worst_fit_node_deletion():
    """
    Test the Worst-Fit scheduling algorithm with node deletion and pod rescheduling.
    
    This test:
    1. Updates config to use worst-fit algorithm
    2. Starts the application
    3. Creates multiple nodes with different capacities
    4. Launches multiple pods on different nodes
    5. Deletes a node with pods and verifies rescheduling using worst-fit
    6. Verifies the pods are placed according to worst-fit logic (node with highest total capacity)
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
        
        # Create nodes in reverse order of capacity to ensure proper placement
        # Node 3 with 4 cores (lowest capacity)
        node3_response = requests.post(f"{api_url}/add-node", json={"cores": 4})
        if node3_response.status_code != 200:
            print(f"Failed to create node 3: {node3_response.text}")
            return False
        
        node3_data = node3_response.json()
        node3_id = node3_data["node_id"]
        print(f"Created node 3: {node3_id} with 4 cores")
        
        # Node 1 with 6 cores (middle capacity)
        node1_response = requests.post(f"{api_url}/add-node", json={"cores": 6})
        if node1_response.status_code != 200:
            print(f"Failed to create node 1: {node1_response.text}")
            return False
        
        node1_data = node1_response.json()
        node1_id = node1_data["node_id"]
        print(f"Created node 1: {node1_id} with 6 cores")
        
        # Node 2 with 8 cores (highest capacity - this will get our initial pods with worst-fit)
        node2_response = requests.post(f"{api_url}/add-node", json={"cores": 8})
        if node2_response.status_code != 200:
            print(f"Failed to create node 2: {node2_response.text}")
            return False
        
        node2_data = node2_response.json()
        node2_id = node2_data["node_id"]
        print(f"Created node 2: {node2_id} with 8 cores")
        
        # Wait for nodes to initialize
        time.sleep(5)
        
        # Step 4: Set up the initial node state with pods on node2
        print("Setting up initial pod allocations...")
        
        # Create pods that should go to node2 (highest capacity with worst-fit)
        pods_to_create = [
            {"pod_id": "node2_pod_1", "cpu": 1},
            {"pod_id": "node2_pod_2", "cpu": 1}
        ]
        
        pod_placements = {}  # Track where pods are placed
        
        for pod_config in pods_to_create:
            pod_id = pod_config["pod_id"]
            cpu = pod_config["cpu"]
            
            pod_response = requests.post(f"{api_url}/launch-pod", json={"pod_id": pod_id, "cpu": cpu})
            if pod_response.status_code != 200:
                print(f"Failed to launch pod {pod_id}: {pod_response.text}")
                return False
            
            pod_data = pod_response.json()
            pod_node = pod_data.get("node_id")
            print(f"Pod {pod_id} ({cpu} cores) placed on node: {pod_node}")
            pod_placements[pod_id] = {"node": pod_node, "cpu": cpu}
        
        # Get initial status to verify setup
        time.sleep(2)
        initial_status_response = requests.get(f"{api_url}/pod-status")
        initial_pod_status = initial_status_response.json()
        print("\nInitial pod status:")
        for node_id, pods in initial_pod_status.items():
            print(f"Node {node_id}:")
            for pod_id, pod_data in pods.items():
                print(f"  - {pod_id}: {pod_data}")
        
        # Calculate available capacity for each node
        node_capacities = {}
        
        nodes_response = requests.get(f"{api_url}/list-nodes")
        nodes_info = nodes_response.json()
        print("\nNode capacities before deletion:")
        for node in nodes_info:
            node_id = node["node_id"]
            capacity = node["capacity"]
            # Calculate used capacity from pods
            used = 0
            if node_id in initial_pod_status:
                for pod_id, pod_data in initial_pod_status[node_id].items():
                    used += pod_data.get("cpu_request", 0)
            available = capacity - used
            node_capacities[node_id] = {"capacity": capacity, "used": used, "available": available}
            print(f"Node {node_id}: capacity={capacity}, used={used}, available={available}")
        
        # Verify at least one pod is on node2
        pods_on_node2 = []
        if node2_id in initial_pod_status:
            pods_on_node2 = list(initial_pod_status[node2_id].keys())
        
        if not pods_on_node2:
            print(f"ERROR: No pods were placed on node {node2_id}, cannot properly test rescheduling")
            return False
            
        print(f"Found {len(pods_on_node2)} pods on node {node2_id}: {', '.join(pods_on_node2)}")
        
        # Now delete node 2 and verify pods are rescheduled according to worst-fit
        print(f"\nDeleting node {node2_id}...")
        delete_response = requests.delete(f"{api_url}/delete-node", json={"node_id": node2_id})
        if delete_response.status_code != 200:
            print(f"Failed to delete node {node2_id}: {delete_response.text}")
            return False
        
        # Print deletion response
        delete_data = delete_response.json()
        print(f"Delete node response: {json.dumps(delete_data, indent=2)}")
        
        # Wait for rescheduling to complete
        time.sleep(5)
        
        # Get final status
        final_status_response = requests.get(f"{api_url}/pod-status")
        final_pod_status = final_status_response.json()
        print("\nFinal pod status after node deletion:")
        for node_id, pods in final_pod_status.items():
            print(f"Node {node_id}:")
            for pod_id, pod_data in pods.items():
                print(f"  - {pod_id}: {pod_data}")
        
        # Check if the rescheduling was successful for each pod from node2
        pods_rescheduled = 0
        
        # Find the node with highest capacity after node2 removal (should be node1)
        highest_capacity_node = max(
            [n for n in node_capacities.keys() if n != node2_id],
            key=lambda n: node_capacities[n]["capacity"]
        )
        
        print(f"Node with highest capacity after deletion: {highest_capacity_node}")
        
        for pod_id in pods_on_node2:
            # Find which node it's on now
            new_node = None
            for node_id, pods in final_pod_status.items():
                if pod_id in pods:
                    new_node = node_id
                    break
            
            if new_node is None:
                print(f"ERROR: Pod {pod_id} was not rescheduled after node deletion")
                return False
            
            print(f"Pod {pod_id} was rescheduled to node: {new_node}")
            
            # With worst-fit, pods should go to the node with most available capacity
            if new_node != highest_capacity_node:
                print(f"ERROR: Pod {pod_id} should be rescheduled to node {highest_capacity_node} but is on {new_node}")
                return False
            
            pods_rescheduled += 1
        
        if pods_rescheduled != len(pods_on_node2):
            print(f"ERROR: Not all pods were successfully rescheduled. Expected {len(pods_on_node2)}, got {pods_rescheduled}")
            return False
        
        print(f"\nSUCCESS: All {pods_rescheduled} pods successfully rescheduled from node {node2_id} to node {highest_capacity_node}")
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

def test_worst_fit_mixed_capacities():
    """
    Test the Worst-Fit algorithm with mixed node capacities and various pod sizes.
    
    This test:
    1. Creates nodes with varying capacities
    2. Partially fills the nodes with pods
    3. Launches new pods with specific CPU requirements
    4. Verifies the worst-fit algorithm places pods on nodes with most remaining capacity
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
        
        # Small node with 4 cores
        small_response = requests.post(f"{api_url}/add-node", json={"cores": 4})
        if small_response.status_code != 200:
            print(f"Failed to create small node: {small_response.text}")
            return False
        
        small_data = small_response.json()
        small_id = small_data["node_id"]
        print(f"Created small node: {small_id} with 4 cores")
        
        # Medium node with 6 cores
        medium_response = requests.post(f"{api_url}/add-node", json={"cores": 6})
        if medium_response.status_code != 200:
            print(f"Failed to create medium node: {medium_response.text}")
            return False
        
        medium_data = medium_response.json()
        medium_id = medium_data["node_id"]
        print(f"Created medium node: {medium_id} with 6 cores")
        
        # Large node with 8 cores
        large_response = requests.post(f"{api_url}/add-node", json={"cores": 8})
        if large_response.status_code != 200:
            print(f"Failed to create large node: {large_response.text}")
            return False
        
        large_data = large_response.json()
        large_id = large_data["node_id"]
        print(f"Created large node: {large_id} with 8 cores")
        
        # Wait for nodes to initialize
        time.sleep(5)
        
        # Step 4: Setup initial allocations on the nodes
        print("Setting up initial pod allocations...")
        
        # Add pods to create a specific setup with small having most capacity
        # node_1 (small): 4 cores free (no pods)
        # node_2 (medium): 3 cores free (add a 3-core pod)
        # node_3 (large): 3 cores free (add a 5-core pod)

        # Add a 3-core pod to node_2
        requests.post(f"{api_url}/launch-pod", json={"pod_id": "init_pod_2", "cpu": 3})
        
        # Add a 5-core pod to node_3
        requests.post(f"{api_url}/launch-pod", json={"pod_id": "init_pod_3", "cpu": 5})
        
        # Get current node capacities to verify setup
        time.sleep(2)
        status_response = requests.get(f"{api_url}/pod-status")
        pod_status = status_response.json()
        
        nodes_response = requests.get(f"{api_url}/list-nodes")
        nodes_info = nodes_response.json()
        print("\nInitial node capacities:")
        node_capacities = {}
        for node in nodes_info:
            node_id = node["node_id"]
            capacity = node["capacity"]
            # Calculate used capacity from pods
            used = 0
            if node_id in pod_status:
                for pod_id, pod_data in pod_status[node_id].items():
                    used += pod_data.get("cpu_request", 0)
            available = capacity - used
            node_capacities[node_id] = {"capacity": capacity, "used": used, "available": available}
            print(f"Node {node_id}: capacity={capacity}, used={used}, available={available}")
        
        # Find the node with the most available capacity for our test
        most_available_node_id = max(node_capacities.items(), key=lambda x: x[1]["available"])[0]
        most_available_capacity = node_capacities[most_available_node_id]["available"]
        print(f"Node with most available capacity: {most_available_node_id} with {most_available_capacity} cores")
        
        # Step 5: Test case 1 - Launch a 2-core pod
        # The worst-fit algorithm should choose the node with most remaining capacity
        print("\nCase 1: Launching 2-core pod...")
        test1_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "test_pod_1", "cpu": 2}
        )
        if test1_response.status_code != 200:
            print(f"Failed to launch test pod 1: {test1_response.text}")
            return False
        
        test1_data = test1_response.json()
        test1_node = test1_data.get("node_id")
        print(f"Test Pod 1 (2 cores) placed on node: {test1_node}")
        
        # Update and display node capacities
        time.sleep(2)
        status_response = requests.get(f"{api_url}/pod-status")
        pod_status = status_response.json()
        
        nodes_response = requests.get(f"{api_url}/list-nodes")
        nodes_info = nodes_response.json()
        print("\nNode capacities after first pod placement:")
        
        # Update node capacities
        for node in nodes_info:
            node_id = node["node_id"]
            capacity = node["capacity"]
            # Calculate used capacity from pods
            used = 0
            if node_id in pod_status:
                for pod_id, pod_data in pod_status[node_id].items():
                    used += pod_data.get("cpu_request", 0)
            available = capacity - used
            node_capacities[node_id] = {"capacity": capacity, "used": used, "available": available}
            print(f"Node {node_id}: capacity={capacity}, used={used}, available={available}")
        
        # Verify Pod 1 placement - should be on the node that had most capacity
        if test1_node != most_available_node_id:
            print(f"ERROR: Worst-fit algorithm failed. Test Pod 1 should be on node {most_available_node_id} but is on {test1_node}")
            return False
        
        # Find the node with the most available capacity for the second test
        most_available_node_id = max(node_capacities.items(), key=lambda x: x[1]["available"])[0]
        most_available_capacity = node_capacities[most_available_node_id]["available"]
        print(f"Node with most available capacity: {most_available_node_id} with {most_available_capacity} cores")
        
        # Check if we have a tie for most available capacity
        tied_nodes = [node_id for node_id, data in node_capacities.items() 
                      if data["available"] == most_available_capacity]
        
        if len(tied_nodes) > 1:
            # When there's a tie, the algorithm should choose the one with the lower node ID
            expected_node_id = min(tied_nodes, key=lambda x: int(x.split('_')[1]))
            print(f"Multiple nodes with same available capacity: {tied_nodes}, should choose: {expected_node_id}")
        else:
            expected_node_id = most_available_node_id
        
        # Step 6: Test case 2 - Launch a 1-core pod
        print("\nCase 2: Launching 1-core pod...")
        test2_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "test_pod_2", "cpu": 1}
        )
        if test2_response.status_code != 200:
            print(f"Failed to launch test pod 2: {test2_response.text}")
            return False
        
        test2_data = test2_response.json()
        test2_node = test2_data.get("node_id")
        print(f"Test Pod 2 (1 core) placed on node: {test2_node}")
        
        # Update and display node capacities
        time.sleep(2)
        status_response = requests.get(f"{api_url}/pod-status")
        pod_status = status_response.json()
        
        nodes_response = requests.get(f"{api_url}/list-nodes")
        nodes_info = nodes_response.json()
        print("\nNode capacities after second pod placement:")
        for node in nodes_info:
            node_id = node["node_id"]
            capacity = node["capacity"]
            # Calculate used capacity from pods
            used = 0
            if node_id in pod_status:
                for pod_id, pod_data in pod_status[node_id].items():
                    used += pod_data.get("cpu_request", 0)
            available = capacity - used
            node_capacities[node_id] = {"capacity": capacity, "used": used, "available": available}
            print(f"Node {node_id}: capacity={capacity}, used={used}, available={available}")
        
        # Verify Pod 2 placement matches expected node
        if test2_node != expected_node_id:
            print(f"ERROR: Worst-fit algorithm failed. Test Pod 2 should be on node {expected_node_id} but is on {test2_node}")
            return False
        
        print("\nSUCCESS: Worst-fit algorithm with mixed capacities works correctly!")
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
    # Run the tests
    print("\n=========== RUNNING TEST: WORST-FIT NODE DELETION ===========\n")
    success1 = test_worst_fit_node_deletion()
    
    print("\n=========== RUNNING TEST: WORST-FIT MIXED CAPACITIES ===========\n")
    success2 = test_worst_fit_mixed_capacities()
    
    # Exit with appropriate status code
    sys.exit(0 if success1 and success2 else 1) 