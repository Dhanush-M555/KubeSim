#!/usr/bin/env python
"""
Real application test for pod rescheduling failure when there's not enough capacity.
This test verifies the system properly reports when pods cannot be rescheduled due to lack of capacity.
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

def test_pod_no_capacity():
    """
    Test that the system properly reports when pods cannot be rescheduled due to lack of capacity.
    This test:
    1. Updates config to disable auto-scaling
    2. Starts the application
    3. Creates two nodes with specific capacities
    4. Launches a large pod on one node
    5. Deletes that node
    6. Verifies that the system correctly reports the pod couldn't be rescheduled
    """
    # Step 1: Update config for testing (with auto-scaling disabled)
    config = {
        "AUTO_SCALE": False,  # Disable auto-scaling
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
        print("Creating first node with capacity 4...")
        node1_response = requests.post(f"{api_url}/add-node", json={"cores": 4})
        if node1_response.status_code != 200:
            print(f"Failed to create first node: {node1_response.text}")
            return False
        
        node1_data = node1_response.json()
        node1_id = node1_data["node_id"]
        print(f"Created node: {node1_id}")
        
        print("Creating second node with capacity 2...")
        node2_response = requests.post(f"{api_url}/add-node", json={"cores": 2})
        if node2_response.status_code != 200:
            print(f"Failed to create second node: {node2_response.text}")
            return False
        
        node2_data = node2_response.json()
        node2_id = node2_data["node_id"]
        print(f"Created node: {node2_id}")
        
        # Wait for nodes to initialize
        time.sleep(5)
        
        # Step 4: Launch a pod that requires 3 CPUs on the first node
        print("Launching pod with 3 CPU requirement on the first node...")
        pod_response = requests.post(
            f"{api_url}/launch-pod",
            json={"pod_id": "large_pod", "cpu": 3}
        )
        if pod_response.status_code != 200:
            print(f"Failed to launch pod: {pod_response.text}")
            return False
        
        # Wait for pod to start
        time.sleep(5)
        
        # Get pod status to verify they're on the expected nodes
        pods_status_response = requests.get(f"{api_url}/pod-status")
        pods_status = pods_status_response.json()
        print("Initial pod status:", json.dumps(pods_status, indent=2))
        
        # Find which node has the pod
        pod_node = None
        for node_id, node_data in pods_status.items():
            if "large_pod" in node_data:
                pod_node = node_id
                break
        
        print(f"Large pod is on node: {pod_node}")
        
        # Step 5: Delete the node with the large pod
        print(f"Deleting node {pod_node}...")
        delete_response = requests.delete(
            f"{api_url}/delete-node",
            json={"node_id": pod_node}
        )
        
        if delete_response.status_code != 200:
            print(f"Failed to delete node: {delete_response.text}")
            return False
        
        delete_result = delete_response.json()
        print("Delete node response:", json.dumps(delete_result, indent=2))
        
        # Wait for a moment
        time.sleep(5)
        
        # Step 6: Verify pod was not rescheduled
        print("Checking final system state...")
        final_status_response = requests.get(f"{api_url}/pod-status")
        final_status = final_status_response.json()
        print("Final pod status:", json.dumps(final_status, indent=2))
        
        # Check if our pod is not present in the final status (it shouldn't be)
        pod_found = False
        for node_id, node_data in final_status.items():
            if "large_pod" in node_data:
                pod_found = True
                break
        
        # Make sure deleted node is gone
        assert pod_node not in final_status, f"Deleted node {pod_node} should not be in final status"
        
        # Verify that the delete response contained information about the failed reschedule
        has_failed_reschedule_info = False
        if "failed_reschedules" in delete_result:
            for failed_pod in delete_result["failed_reschedules"]:
                if failed_pod["pod_id"] == "large_pod":
                    has_failed_reschedule_info = True
                    break
        
        # We expect the pod to NOT be rescheduled, so it should:
        # 1. NOT be found in final_status
        # 2. BE reported in failed_reschedules
        if not pod_found and has_failed_reschedule_info:
            print("SUCCESS: System correctly reported that the pod could not be rescheduled!")
            return True
        else:
            issues = []
            if pod_found:
                issues.append("Pod was rescheduled when it shouldn't have been")
            if not has_failed_reschedule_info:
                issues.append("System did not report the failed rescheduling")
            
            print(f"FAILURE: Test failed with issues: {', '.join(issues)}")
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
    success = test_pod_no_capacity()
    
    # Exit with appropriate status code
    sys.exit(0 if success else 1) 