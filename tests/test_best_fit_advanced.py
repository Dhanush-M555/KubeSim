#!/usr/bin/env python
"""
Advanced real application test for the Best-Fit scheduling algorithm.
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

def test_best_fit_node_deletion():
    """
    Test the Best-Fit scheduling algorithm with node deletion and pod rescheduling.
    
    This test:
    1. Updates config to use best-fit algorithm
    2. Starts the application
    3. Creates multiple nodes with different capacities
    4. Launches multiple pods on different nodes
    5. Deletes a node with pods and verifies rescheduling using best-fit
    6. Verifies the pods are placed according to best-fit logic (node with least remaining capacity)
    """
    # Step 1: Update config for testing
    config = {
        "AUTO_SCALE": False,  # Disable auto-scaling
        "SCHEDULING_ALGO": "best-fit",  # Set algorithm to best-fit
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
        
        # Step 4: Set up the initial node state with specific allocations
        # Node 1 (4 cores): Start with 2 cores used (2 available)
        # Node 2 (6 cores): Start with 3 cores used (3 available) - this node will be deleted
        # Node 3 (8 cores): Start with 6 cores used (2 available)
        print("Setting up initial pod allocations...")
        
        # Node 1: Use 2 cores
        node1_pod_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "node1_pod_1", "cpu": 2}
        )
        if node1_pod_response.status_code != 200:
            print(f"Failed to launch pod on node 1: {node1_pod_response.text}")
            return False
        
        # Node 2: Use 3 cores with multiple pods (this node will be deleted)
        pods_on_node2 = [
            {"pod_id": "node2_pod_1", "cpu": 1},
            {"pod_id": "node2_pod_2", "cpu": 2}
        ]
        
        pod_placements = {}  # Track where pods are placed
        
        for pod_config in pods_on_node2:
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
        
        # Node 3: Use 6 cores
        node3_pod_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "node3_pod_1", "cpu": 6}
        )
        if node3_pod_response.status_code != 200:
            print(f"Failed to launch pod on node 3: {node3_pod_response.text}")
            return False
        
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
        
        # Now delete node 2 and verify pods are rescheduled according to best-fit
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
        
        # Verify pods were rescheduled according to best-fit
        # For each pod that was on node2, verify it was placed on the node that would have the least remaining capacity
        
        # First, update node capacities after deletion
        updated_node_capacities = {}
        updated_nodes_response = requests.get(f"{api_url}/list-nodes")
        for node in updated_nodes_response.json():
            node_id = node["node_id"]
            if node_id != node2_id:  # Skip the deleted node
                updated_node_capacities[node_id] = node_capacities[node_id]
        
        # Then, check each rescheduled pod from node2
        for pod_id, pod_info in pod_placements.items():
            if pod_info["node"] == node2_id:  # This pod was on the deleted node
                cpu_request = pod_info["cpu"]
                
                # Find which node it's on now
                new_node = None
                for node_id, pods in final_pod_status.items():
                    if pod_id in pods:
                        new_node = node_id
                        break
                
                if new_node is None:
                    print(f"ERROR: Pod {pod_id} was not rescheduled after node deletion")
                    return False
                
                print(f"Pod {pod_id} ({cpu_request} cores) was rescheduled to node: {new_node}")
                
                # For best-fit, we expect pods to be placed on the node that would have the smallest remaining capacity
                # Node 1: 2 cores used, 2 available
                # Node 3: 6 cores used, 2 available
                # Both nodes have the same available capacity, so tie breaking should look at total capacity
                # and place pods on the node with higher capacity (Node 3)
                
                # For a 1-core pod, both nodes would have 1 core remaining, so it should go to Node 3 (higher capacity)
                # For a 2-core pod, both nodes would have 0 cores remaining, so it should go to Node 3 (higher capacity)
                
                expected_node = node3_id  # Node 3 has higher total capacity for tie-breaking
                
                if new_node != expected_node:
                    print(f"ERROR: Best-fit rescheduling failed. Pod {pod_id} should be on node {expected_node} but is on {new_node}")
                    return False
                
                # Update the available capacity for the node that got the pod
                updated_node_capacities[new_node]["used"] += cpu_request
                updated_node_capacities[new_node]["available"] -= cpu_request
        
        print("\nSUCCESS: Best-fit rescheduling works correctly!")
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

def test_best_fit_varying_loads():
    """
    Test the Best-Fit algorithm with varying pod loads to ensure it correctly 
    places pods on nodes with the least remaining capacity.
    
    This test:
    1. Creates multiple nodes with different initial loads
    2. Launches pods with different resource requirements
    3. Verifies the best-fit algorithm places pods on nodes that will have the least remaining capacity
    4. Tests edge cases with identical remaining capacities to check tie-breaking
    """
    # Step 1: Update config for testing
    config = {
        "AUTO_SCALE": False,  # Disable auto-scaling
        "SCHEDULING_ALGO": "best-fit",  # Set algorithm to best-fit
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
        
        # Small node with 3 cores
        small_response = requests.post(f"{api_url}/add-node", json={"cores": 3})
        if small_response.status_code != 200:
            print(f"Failed to create small node: {small_response.text}")
            return False
        
        small_data = small_response.json()
        small_id = small_data["node_id"]
        print(f"Created small node: {small_id} with 3 cores")
        
        # Medium node with 5 cores
        medium_response = requests.post(f"{api_url}/add-node", json={"cores": 5})
        if medium_response.status_code != 200:
            print(f"Failed to create medium node: {medium_response.text}")
            return False
        
        medium_data = medium_response.json()
        medium_id = medium_data["node_id"]
        print(f"Created medium node: {medium_id} with 5 cores")
        
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
        
        # Step 4: Set up initial pod allocations to create specific remaining capacities
        # Small node (3 cores): Use 0 cores -> 3 cores remaining
        # Medium node (5 cores): Use 2 cores -> 3 cores remaining
        # Large node (8 cores): Use 3 cores -> 5 cores remaining
        print("Setting up initial pod allocations...")
        
        # Medium node: Use 2 cores
        medium_pod_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "medium_pod_1", "cpu": 2}
        )
        if medium_pod_response.status_code != 200:
            print(f"Failed to launch pod on medium node: {medium_pod_response.text}")
            return False
        
        # Large node: Use 3 cores
        large_pod_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "large_pod_1", "cpu": 3}
        )
        if large_pod_response.status_code != 200:
            print(f"Failed to launch pod on large node: {large_pod_response.text}")
            return False
        
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
        
        # Step 5: Test case 1 - Launch a 2-core pod
        # Expected behavior: Pod should go to small or medium node (both have 3 cores available)
        # But medium has higher capacity, so medium should win according to tie-breaking
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
        
        # Verify Pod 1 placement
        expected_node = medium_id  # Both small and medium have 3 cores, but medium has higher capacity
        if test1_node != expected_node:
            print(f"ERROR: Best-fit algorithm failed. Test Pod 1 should be on node {expected_node} but is on {test1_node}")
            return False
        
        # Step 6: Test case 2 - Launch a 1-core pod
        # Expected behavior: Pod should go to small node (1 core available),
        # because medium node will have 1 core available after the previous pod placement
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
        
        # Verify Pod 2 placement - should be on small node for least remaining capacity
        expected_node = small_id
        if test2_node != expected_node:
            print(f"ERROR: Best-fit algorithm failed. Test Pod 2 should be on node {expected_node} but is on {test2_node}")
            return False
        
        # Step 7: Test case 3 - Launch a 3-core pod
        # Expected behavior: Pod should go to large node (only node with sufficient capacity)
        print("\nCase 3: Launching 3-core pod...")
        test3_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "test_pod_3", "cpu": 3}
        )
        if test3_response.status_code != 200:
            print(f"Failed to launch test pod 3: {test3_response.text}")
            return False
        
        test3_data = test3_response.json()
        test3_node = test3_data.get("node_id")
        print(f"Test Pod 3 (3 cores) placed on node: {test3_node}")
        
        # Verify Pod 3 placement - should be on large node (only one with enough capacity)
        expected_node = large_id
        if test3_node != expected_node:
            print(f"ERROR: Best-fit algorithm failed. Test Pod 3 should be on node {expected_node} but is on {test3_node}")
            return False
        
        # Step 8: Test case 4 - Launch a 2-core pod
        # Expected behavior: Pod should go to large node (now it has 2 cores left)
        print("\nCase 4: Launching another 2-core pod...")
        test4_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "test_pod_4", "cpu": 2}
        )
        if test4_response.status_code != 200:
            print(f"Failed to launch test pod 4: {test4_response.text}")
            return False
        
        test4_data = test4_response.json()
        test4_node = test4_data.get("node_id")
        print(f"Test Pod 4 (2 cores) placed on node: {test4_node}")
        
        # Verify Pod 4 placement
        expected_node = large_id
        if test4_node != expected_node:
            print(f"ERROR: Best-fit algorithm failed. Test Pod 4 should be on node {expected_node} but is on {test4_node}")
            return False
        
        # Get final status for verification
        final_status_response = requests.get(f"{api_url}/pod-status")
        final_pod_status = final_status_response.json()
        print("\nFinal pod status:")
        for node_id, pods in final_pod_status.items():
            print(f"Node {node_id}:")
            for pod_id, pod_data in pods.items():
                print(f"  - {pod_id}: {pod_data}")
        
        print("\nSUCCESS: Best-fit algorithm with varying loads works correctly!")
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
    print("\n=========== RUNNING TEST: BEST-FIT NODE DELETION ===========\n")
    success1 = test_best_fit_node_deletion()
    
    print("\n=========== RUNNING TEST: BEST-FIT VARYING LOADS ===========\n")
    success2 = test_best_fit_varying_loads()
    
    # Exit with appropriate status code
    sys.exit(0 if success1 and success2 else 1) 