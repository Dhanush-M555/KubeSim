#!/usr/bin/env python
"""
Advanced real application test for the First-Fit scheduling algorithm.
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

def test_first_fit_node_deletion():
    """
    Test the First-Fit scheduling algorithm with node deletion and pod rescheduling.
    
    This test:
    1. Updates config to use first-fit algorithm
    2. Starts the application
    3. Creates multiple nodes with different capacities
    4. Launches multiple pods on different nodes
    5. Deletes a node with pods and verifies rescheduling using first-fit
    6. Verifies the pods are placed according to first-fit logic (first node with sufficient capacity)
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
        
        # Step 4: Launch multiple pods on node 2 (the middle node)
        print("Launching pods on node 2...")
        
        # Launch 3 pods with different CPU requirements on node 2
        pods_on_node2 = [
            {"pod_id": "pod_1", "cpu": 1},
            {"pod_id": "pod_2", "cpu": 2},
            {"pod_id": "pod_3", "cpu": 2}
        ]
        
        # Track pod placements
        pod_placements = {}
        
        for pod_config in pods_on_node2:
            pod_id = pod_config["pod_id"]
            cpu = pod_config["cpu"]
            
            # Launch pod
            pod_response = requests.post(f"{api_url}/launch-pod", json={"pod_id": pod_id, "cpu": cpu})
            if pod_response.status_code != 200:
                print(f"Failed to launch pod {pod_id}: {pod_response.text}")
                return False
            
            # Check pod placement
            pod_data = pod_response.json()
            pod_node = pod_data.get("node_id")
            print(f"Pod {pod_id} ({cpu} cores) placed on node: {pod_node}")
            pod_placements[pod_id] = {"node": pod_node, "cpu": cpu}
        
        # Get initial status and confirm pods are launched correctly
        time.sleep(2)
        initial_status_response = requests.get(f"{api_url}/pod-status")
        initial_pod_status = initial_status_response.json()
        print("\nInitial pod status:")
        for node_id, pods in initial_pod_status.items():
            print(f"Node {node_id}:")
            for pod_id, pod_data in pods.items():
                print(f"  - {pod_id}: {pod_data}")
        
        # Step 5: Delete node 2 and verify pod rescheduling
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
        
        # Step 6: Check if pods were rescheduled according to first-fit
        final_status_response = requests.get(f"{api_url}/pod-status")
        final_pod_status = final_status_response.json()
        print("\nFinal pod status after node deletion:")
        for node_id, pods in final_pod_status.items():
            print(f"Node {node_id}:")
            for pod_id, pod_data in pods.items():
                print(f"  - {pod_id}: {pod_data}")
        
        # Also get node capacities
        nodes_response = requests.get(f"{api_url}/list-nodes")
        nodes_info = {}
        for node in nodes_response.json():
            node_id = node["node_id"]
            nodes_info[node_id] = {"capacity": node["capacity"]}
        
        # Verify pods were rescheduled according to first-fit (first node with sufficient capacity)
        # We expect pod_1 (1 core) to go to node_1 (first with sufficient capacity)
        # and pod_2 and pod_3 (2 cores) to go to node_3 (node_1 would be filled after pod_1)
        
        # Check each pod that was on node2
        for pod_id, pod_info in pod_placements.items():
            if pod_info["node"] == node2_id:  # This pod was on the deleted node
                cpu_request = pod_info["cpu"]
                
                # Find which node it is now on
                new_node = None
                for node_id, pods in final_pod_status.items():
                    if pod_id in pods:
                        new_node = node_id
                        break
                
                if new_node is None:
                    print(f"ERROR: Pod {pod_id} was not rescheduled after node deletion")
                    return False
                
                print(f"Pod {pod_id} ({cpu_request} cores) was rescheduled to node: {new_node}")
                
                # For first-fit, we expect the pod to be on the first node with sufficient capacity
                expected_node = None
                
                if cpu_request <= 1 and node1_id in nodes_info:
                    # pod_1 (1 core) should go to node_1 
                    expected_node = node1_id
                else:
                    # pod_2 and pod_3 (2 cores each) should go to node_3
                    expected_node = node3_id
                
                if new_node != expected_node:
                    print(f"ERROR: First-fit rescheduling failed. Pod {pod_id} should be on node {expected_node} but is on {new_node}")
                    return False
        
        print("\nSUCCESS: First-fit rescheduling works correctly!")
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

def test_first_fit_mixed_capacities():
    """
    Test the First-Fit algorithm with nodes of mixed capacities and pods with varying requirements.
    
    This test:
    1. Creates nodes with different capacities: small, medium, large
    2. Fills them partially with pods
    3. Launches new pods with specific requirements
    4. Verifies the first-fit algorithm correctly places them on the first node with enough capacity
    5. Tests edge cases like pods that only fit on the largest node
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
        
        # Small node with 2 cores
        small_response = requests.post(f"{api_url}/add-node", json={"cores": 2})
        if small_response.status_code != 200:
            print(f"Failed to create small node: {small_response.text}")
            return False
        
        small_data = small_response.json()
        small_id = small_data["node_id"]
        print(f"Created small node: {small_id} with 2 cores")
        
        # Medium node with 4 cores
        medium_response = requests.post(f"{api_url}/add-node", json={"cores": 4})
        if medium_response.status_code != 200:
            print(f"Failed to create medium node: {medium_response.text}")
            return False
        
        medium_data = medium_response.json()
        medium_id = medium_data["node_id"]
        print(f"Created medium node: {medium_id} with 4 cores")
        
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
        
        # Step 4: Partially fill nodes to set up test cases
        print("Setting up initial pod allocations...")
        
        # Fill small node with 1 core, leaving 1 core free
        small_pod_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "small_pod_1", "cpu": 1}
        )
        if small_pod_response.status_code != 200:
            print(f"Failed to launch pod on small node: {small_pod_response.text}")
            return False
        
        # Fill medium node with 2 cores, leaving 2 cores free
        medium_pod_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "medium_pod_1", "cpu": 2}
        )
        if medium_pod_response.status_code != 200:
            print(f"Failed to launch pod on medium node: {medium_pod_response.text}")
            return False
        
        # Fill large node with 3 cores, leaving 5 cores free
        large_pod_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "large_pod_1", "cpu": 3}
        )
        if large_pod_response.status_code != 200:
            print(f"Failed to launch pod on large node: {large_pod_response.text}")
            return False
        
        # Get current status to verify setup
        time.sleep(2)
        status_response = requests.get(f"{api_url}/pod-status")
        pod_status = status_response.json()
        print("\nInitial pod status:")
        for node_id, pods in pod_status.items():
            print(f"Node {node_id}:")
            for pod_id, pod_data in pods.items():
                print(f"  - {pod_id}: {pod_data}")
        
        # Step 5: Test various pod placements
        
        # Test case 1: 1-core pod should go to small node (first fit)
        print("\nCase 1: Launching 1-core pod...")
        test1_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "test_pod_1", "cpu": 1}
        )
        if test1_response.status_code != 200:
            print(f"Failed to launch test pod 1: {test1_response.text}")
            return False
        
        test1_data = test1_response.json()
        test1_node = test1_data.get("node_id")
        print(f"Test Pod 1 (1 core) placed on node: {test1_node}")
        
        # First-fit should have placed it on small node
        if test1_node != small_id:
            print(f"ERROR: First-fit algorithm failed. Pod should be on {small_id} but is on {test1_node}")
            return False
        
        # Test case 2: 2-core pod should go to medium node (small is full now)
        print("\nCase 2: Launching 2-core pod...")
        test2_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "test_pod_2", "cpu": 2}
        )
        if test2_response.status_code != 200:
            print(f"Failed to launch test pod 2: {test2_response.text}")
            return False
        
        test2_data = test2_response.json()
        test2_node = test2_data.get("node_id")
        print(f"Test Pod 2 (2 cores) placed on node: {test2_node}")
        
        # First-fit should have placed it on medium node
        if test2_node != medium_id:
            print(f"ERROR: First-fit algorithm failed. Pod should be on {medium_id} but is on {test2_node}")
            return False
        
        # Test case 3: 4-core pod should go to large node (others don't have capacity)
        print("\nCase 3: Launching 4-core pod...")
        test3_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "test_pod_3", "cpu": 4}
        )
        if test3_response.status_code != 200:
            print(f"Failed to launch test pod 3: {test3_response.text}")
            return False
        
        test3_data = test3_response.json()
        test3_node = test3_data.get("node_id")
        print(f"Test Pod 3 (4 cores) placed on node: {test3_node}")
        
        # First-fit should have placed it on large node
        if test3_node != large_id:
            print(f"ERROR: First-fit algorithm failed. Pod should be on {large_id} but is on {test3_node}")
            return False
        
        # Get final status to verify placements
        final_status_response = requests.get(f"{api_url}/pod-status")
        final_pod_status = final_status_response.json()
        print("\nFinal pod status:")
        for node_id, pods in final_pod_status.items():
            print(f"Node {node_id}:")
            for pod_id, pod_data in pods.items():
                print(f"  - {pod_id}: {pod_data}")
        
        print("\nSUCCESS: First-fit algorithm with mixed capacities works correctly!")
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
    print("\n=========== RUNNING TEST: FIRST-FIT NODE DELETION ===========\n")
    success1 = test_first_fit_node_deletion()
    
    print("\n=========== RUNNING TEST: FIRST-FIT MIXED CAPACITIES ===========\n")
    success2 = test_first_fit_mixed_capacities()
    
    # Exit with appropriate status code
    sys.exit(0 if success1 and success2 else 1) 