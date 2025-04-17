import os
import json
import time
import threading
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS  # Import CORS
import docker
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Load configuration
with open('config.json', 'r') as config_file:
    config = json.load(config_file)
    AUTO_SCALE = config.get('AUTO_SCALE', False)
    SCHEDULING_ALGO = config.get('SCHEDULING_ALGO', 'first-fit')
    DEFAULT_NODE_CAPACITY = config.get('DEFAULT_NODE_CAPACITY', 4)  # Default cores per node
    AUTO_SCALE_HIGH_THRESHOLD = config.get('AUTO_SCALE_HIGH_THRESHOLD', 80)  # Percentage
    AUTO_SCALE_LOW_THRESHOLD = config.get('AUTO_SCALE_LOW_THRESHOLD', 20)  # Percentage
    HEAVENLY_RESTRICTION = config.get('HEAVENLY_RESTRICTION', False)
    
    print(f"Config loaded: AUTO_SCALE={AUTO_SCALE}, SCHEDULING_ALGO={SCHEDULING_ALGO}, " 
          f"DEFAULT_NODE_CAPACITY={DEFAULT_NODE_CAPACITY}, HEAVENLY_RESTRICTION={HEAVENLY_RESTRICTION}")

# Initialize Docker client
docker_client = docker.from_env()

# Node management
nodes = {}  # {node_id: {"container": container, "last_heartbeat": timestamp, "pod_health": {}, "capacity": cores}}
cached_status = {}  # {node_id: {pod_id: {"cpu_usage": value, "healthy": bool, "cpu_request": value}}}
node_counter = 0

# Mutex for thread safety
nodes_lock = threading.Lock()
cached_status_lock = threading.Lock()

def poll_metrics():
    """Background thread to poll node metrics every 15s"""
    while True:
        with nodes_lock:
            # Create a copy of nodes with container and node_id
            local_nodes = {node_id: node_data["container"] for node_id, node_data in nodes.items()}
        
        for node_id, container in local_nodes.items():
            try:
                # Get container IP address instead of using hostname
                container_info = docker_client.api.inspect_container(container.id)
                container_ip = container_info['NetworkSettings']['Networks']['cluster-net']['IPAddress']
                
                response = requests.get(f"http://{container_ip}:5001/metrics", timeout=5)
                if response.status_code == 200:
                    metrics = response.json()
                    
                    with nodes_lock:
                        if node_id in nodes:
                            node_health = nodes[node_id]["pod_health"]
                    
                    with cached_status_lock:
                        cached_status[node_id] = {}
                        # Skip node info key which starts with underscore
                        for pod_id, pod_metrics in metrics.items():
                            if pod_id.startswith('_'):  # Skip special keys like _node_info
                                continue
                                
                            # Handle the new metrics format with error checking
                            try:
                                is_healthy = node_health.get(pod_id, True)
                                
                                # Set cpu_usage to -1 when pod is unhealthy for better visualization on graphs
                                cpu_usage = pod_metrics.get("cpu_usage", 0)
                                if not is_healthy:
                                    cpu_usage = -1
                                
                                cached_status[node_id][pod_id] = {
                                    "cpu_usage": cpu_usage,
                                    "healthy": is_healthy,
                                    "cpu_request": pod_metrics.get("cpu_request", 1),
                                    "restricted": pod_metrics.get("restricted", False)
                                }
                            except Exception as e:
                                print(f"Error processing metrics for pod {pod_id}: {str(e)}")
                                print(f"Pod metrics: {pod_metrics}")
            except (requests.exceptions.RequestException, docker.errors.APIError) as e:
                print(f"Error polling metrics from {node_id}: {str(e)}")
                # Node might be down or unreachable
                with cached_status_lock:
                    if node_id in cached_status:
                        for pod_id in cached_status[node_id]:
                            cached_status[node_id][pod_id]["healthy"] = False
                            # Set cpu_usage to -1 for unhealthy pods
                            cached_status[node_id][pod_id]["cpu_usage"] = -1
        
        # Auto-scaling check
        if AUTO_SCALE:
            check_auto_scaling()
        
        time.sleep(15)

def check_auto_scaling():
    """Check if we need to scale up or down based on CPU usage"""
    total_cpu_usage = 0
    total_capacity = 0
    node_usage = {}
    
    with cached_status_lock:
        with nodes_lock:
            for node_id, node_data in nodes.items():
                node_capacity = node_data.get("capacity", DEFAULT_NODE_CAPACITY)
                
                # Calculate node CPU usage
                node_pods = cached_status.get(node_id, {})
                # Sum CPU usage only for healthy pods (where cpu_usage is not -1)
                node_cpu = sum(pod["cpu_usage"] for pod in node_pods.values() 
                              if pod["cpu_usage"] >= 0)
                
                total_cpu_usage += node_cpu
                total_capacity += node_capacity
                node_usage[node_id] = node_cpu
    
    if not node_usage:  # No nodes yet
        return
    
    usage_percent = (total_cpu_usage / total_capacity) * 100 if total_capacity > 0 else 0
    
    if usage_percent > AUTO_SCALE_HIGH_THRESHOLD:
        # Add a node when usage > threshold
        print(f"AUTO-SCALING UP: Usage at {usage_percent:.1f}% exceeded threshold of {AUTO_SCALE_HIGH_THRESHOLD}%")
        add_node(auto_scaled=True)
    elif usage_percent < AUTO_SCALE_LOW_THRESHOLD and len(node_usage) > 1:
        # Remove least loaded node when usage < threshold
        least_loaded = min(node_usage.items(), key=lambda x: x[1])
        print(f"AUTO-SCALING DOWN: Usage at {usage_percent:.1f}% below threshold of {AUTO_SCALE_LOW_THRESHOLD}%")
        print(f"Removing least loaded node: {least_loaded[0]}")
        remove_node(least_loaded[0])

def remove_node(node_id):
    """Remove a node from the cluster"""
    
    # First capture the pods on this node before removal
    pods_to_reschedule = {}
    with cached_status_lock:
        if node_id in cached_status:
            for pod_id, pod_data in cached_status[node_id].items():
                pods_to_reschedule[pod_id] = pod_data["cpu_request"]
    
    # Remove the node
    with nodes_lock:
        if node_id in nodes:
            try:
                container = nodes[node_id]["container"]
                try:
                    container.stop()
                except Exception as e:
                    print(f"Warning: Could not stop container for node {node_id}: {e}")
                
                try:
                    container.remove()
                except Exception as e:
                    print(f"Warning: Could not remove container for node {node_id}: {e}")
                
                del nodes[node_id]
            except Exception as e:
                print(f"Error removing node {node_id}: {e}")
    
    with cached_status_lock:
        if node_id in cached_status:
            del cached_status[node_id]
    
    # Reschedule pods from the deleted node if any exist
    failed_reschedules = []
    if pods_to_reschedule:
        print(f"Attempting to reschedule {len(pods_to_reschedule)} pods from deleted node {node_id}")
        
        for pod_id, cpu_request in pods_to_reschedule.items():
            try:
                success = reschedule_pod(pod_id, cpu_request)
                if success:
                    print(f"Successfully rescheduled pod {pod_id} from deleted node {node_id}")
                else:
                    print(f"Failed to reschedule pod {pod_id} from deleted node {node_id}")
                    failed_reschedules.append({"pod_id": pod_id, "cpu_request": cpu_request})
            except Exception as e:
                print(f"Error during rescheduling of pod {pod_id}: {str(e)}")
                failed_reschedules.append({"pod_id": pod_id, "cpu_request": cpu_request})
    
    return True, failed_reschedules

@app.route('/add-node', methods=['POST'])
def add_node(auto_scaled=False):
    """Add a new node to the cluster"""
    global node_counter
    
    # Get the node capacity from request or use default
    data = request.json or {}
    cores = data.get('cores', DEFAULT_NODE_CAPACITY)
    
    # Validate cores is an integer > 0
    try:
        cores = int(cores)
        if cores <= 0:
            return jsonify({"status": "error", "message": "Cores must be a positive integer"}), 400
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Cores must be a positive integer"}), 400
    
    node_counter += 1
    node_id = f"node_{node_counter}"
    
    try:
        # Create data directory if it doesn't exist
        os.makedirs("/var/cluster-data", exist_ok=True)
        
        # Copy config to shared volume to ensure nodes can access it
        try:
            with open("config.json", "r") as src_file:
                config_data = json.load(src_file)
                
            # Make sure HEAVENLY_RESTRICTION is set to true
            config_data["HEAVENLY_RESTRICTION"] = HEAVENLY_RESTRICTION
            
            with open("/var/cluster-data/config.json", "w") as dest_file:
                json.dump(config_data, dest_file, indent=2)
                
            print(f"Successfully copied config to shared volume with HEAVENLY_RESTRICTION={HEAVENLY_RESTRICTION}")
        except Exception as e:
            print(f"Warning: Could not copy config to shared volume: {str(e)}")
        
        # Check if container with this name already exists and remove it
        try:
            existing_container = docker_client.containers.get(node_id)
            print(f"Container {node_id} already exists, stopping and removing it")
            existing_container.stop()
            existing_container.remove()
        except docker.errors.NotFound:
            # Container doesn't exist, which is fine
            pass
        
        # Ensure the network exists
        try:
            docker_client.networks.get("cluster-net")
        except docker.errors.NotFound:
            print("Creating cluster-net network")
            docker_client.networks.create("cluster-net", driver="bridge")
        
        # Run a new Docker container
        container = docker_client.containers.run(
            "node_image",
            name=node_id,
            network="cluster-net",
            volumes={"/var/cluster-data": {"bind": "/data", "mode": "rw"}},
            environment={"NODE_ID": node_id, "NODE_CAPACITY": str(cores)},
            detach=True
        )
        
        source = "auto-scaling" if auto_scaled else "manual request"
        print(f"Successfully created container {node_id} with {cores} cores via {source}")
        
        # Record the node with its capacity
        with nodes_lock:
            nodes[node_id] = {
                "container": container,
                "last_heartbeat": time.time(),
                "pod_health": {},
                "capacity": cores
            }
        
        # Allow some time for the node to start up before using it
        time.sleep(1)
        
        return jsonify({"status": "success", "node_id": node_id, "capacity": cores, "auto_scaled": auto_scaled})
    
    except docker.errors.APIError as e:
        print(f"Docker API error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
    except Exception as e:
        print(f"Unexpected error adding node: {str(e)}")
        return jsonify({"status": "error", "message": f"Unexpected error: {str(e)}"}), 500

@app.route('/launch-pod', methods=['POST'])
def launch_pod():
    """Schedule a pod on a node using the configured scheduling algorithm"""
    data = request.json
    
    # Validate CPU request
    try:
        cpu_request = int(data.get('cpu', 1))
        if cpu_request <= 0:
            return jsonify({"status": "error", "message": "CPU request must be a positive integer"}), 400
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "CPU request must be a positive integer"}), 400
    
    pod_id = data.get('pod_id', f"pod_{int(time.time())}")
    
    # Check if we have any nodes
    with nodes_lock:
        if not nodes:
            if AUTO_SCALE:
                # Add a node if auto-scaling is enabled
                print(f"No nodes available. Auto-creating a node for pod {pod_id} with {cpu_request} CPU cores")
                response = add_node(auto_scaled=True)
                if isinstance(response, tuple) and len(response) > 1:
                    # Error occurred
                    return response
                # Get the new node
                node_data = response.get_json()
                if not node_data or 'node_id' not in node_data:
                    return jsonify({"status": "error", "message": "Failed to add node"}), 500
                
                # Allow some time for the node to start
                time.sleep(2)
                
            else:
                return jsonify({"status": "error", "message": "No nodes available, and auto-scaling is disabled"}), 400
    
    # Get current CPU allocation for each node based on pod requests (not actual usage)
    with nodes_lock:
        node_allocations = {}
        for node_id, node_data in nodes.items():
            node_capacity = node_data.get("capacity", DEFAULT_NODE_CAPACITY)
            
            # Get all pods on this node and sum their CPU requests
            node_pods = {}
            with cached_status_lock:
                node_pods = cached_status.get(node_id, {})
            
            # Calculate total CPU requests for this node
            total_cpu_requests = sum(pod.get("cpu_request", 0) for pod in node_pods.values())
            
            # Store allocation data
            node_allocations[node_id] = {
                "allocated": total_cpu_requests,
                "capacity": node_capacity,
                "available": node_capacity - total_cpu_requests
            }
            
            print(f"Node {node_id}: {total_cpu_requests}/{node_capacity} cores allocated, {node_capacity - total_cpu_requests} available")
    
    target_node = None
    
    if SCHEDULING_ALGO == "first-fit":
        # First node with enough capacity
        for node_id, alloc_data in node_allocations.items():
            if alloc_data["available"] >= cpu_request:
                target_node = node_id
                print(f"Found suitable node {node_id} with {alloc_data['available']} cores available for pod requesting {cpu_request} cores")
                break
    
    elif SCHEDULING_ALGO == "best-fit":
        # Node with smallest remaining capacity after adding the pod
        best_fit = None
        smallest_remaining = float('inf')
        
        for node_id, alloc_data in node_allocations.items():
            if alloc_data["available"] >= cpu_request:
                remaining = alloc_data["available"] - cpu_request
                if remaining < smallest_remaining:
                    smallest_remaining = remaining
                    best_fit = node_id
        
        target_node = best_fit
    
    elif SCHEDULING_ALGO == "worst-fit":
        # Node with most remaining capacity after adding the pod
        worst_fit = None
        largest_remaining = -1
        
        for node_id, alloc_data in node_allocations.items():
            if alloc_data["available"] >= cpu_request:
                remaining = alloc_data["available"] - cpu_request
                if remaining > largest_remaining:
                    largest_remaining = remaining
                    worst_fit = node_id
        
        target_node = worst_fit
    
    # If no node has capacity, add a new one if auto-scaling is enabled
    if target_node is None:
        if AUTO_SCALE:
            # Create a new node with enough capacity for this pod
            print(f"No node with sufficient capacity for pod {pod_id} requesting {cpu_request} CPU cores. Auto-creating a new node.")
            response = add_node(auto_scaled=True)
            if isinstance(response, tuple) and len(response) > 1:
                # Error occurred
                return response
            node_data = response.get_json()
            target_node = node_data.get("node_id")
            
            # Allow some time for the node to start
            time.sleep(2)
        else:
            return jsonify({"status": "error", "message": f"No node with sufficient capacity for pod requesting {cpu_request} cores"}), 400
    
    # Send the pod to the target node
    try:
        # Check container is running first
        with nodes_lock:
            if target_node not in nodes:
                return jsonify({"status": "error", "message": f"Node {target_node} not found"}), 400
            
            container = nodes[target_node]["container"]
            # Skip the status check which might be causing issues
            # if container.status != "running":
            #     return jsonify({"status": "error", "message": f"Node {target_node} is not running"}), 400
        
        print(f"Attempting to launch pod {pod_id} on node {target_node} with {cpu_request} CPU cores")
        
        # Multiple attempts with exponential backoff
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                # Get container IP address instead of using hostname
                with nodes_lock:
                    container = nodes[target_node]["container"]
                    container_info = docker_client.api.inspect_container(container.id)
                    container_ip = container_info['NetworkSettings']['Networks']['cluster-net']['IPAddress']
                
                response = requests.post(
                    f"http://{container_ip}:5001/add-pod",
                    json={"pod_id": pod_id, "cpu_request": cpu_request},
                    timeout=5
                )
                
                if response.status_code == 200:
                    print(f"Successfully launched pod {pod_id} on node {target_node}")
                    
                    # Update node allocations with the new pod's CPU request
                    with nodes_lock:
                        if target_node in node_allocations:
                            node_allocations[target_node]['allocated'] += cpu_request
                            node_allocations[target_node]['available'] -= cpu_request
                    
                    # Also update cached_status to include the new pod
                    with cached_status_lock:
                        if target_node not in cached_status:
                            cached_status[target_node] = {}
                        
                        cached_status[target_node][pod_id] = {
                            'cpu_request': cpu_request,
                            'cpu_usage': 0,  # Initial usage is 0
                            'healthy': True
                        }
                    
                    return jsonify({"status": "success", "pod_id": pod_id, "node_id": target_node})
                else:
                    print(f"Attempt {attempt}/{max_attempts}: Node error: {response.text}")
                    if attempt == max_attempts:
                        return jsonify({"status": "error", "message": f"Node error: {response.text}"}), 400
            except requests.exceptions.RequestException as e:
                print(f"Attempt {attempt}/{max_attempts}: Cannot reach node: {str(e)}")
                if attempt == max_attempts:
                    return jsonify({"status": "error", "message": f"Cannot reach node: {str(e)}"}), 500
            
            # Exponential backoff
            if attempt < max_attempts:
                backoff_time = 2 ** (attempt - 1)
                print(f"Retrying in {backoff_time} seconds...")
                time.sleep(backoff_time)
        
        return jsonify({"status": "error", "message": "Failed to launch pod after multiple attempts"}), 500
    
    except Exception as e:
        print(f"Unexpected error launching pod: {str(e)}")
        return jsonify({"status": "error", "message": f"Unexpected error: {str(e)}"}), 500

@app.route('/pod-status', methods=['GET'])
def pod_status():
    """Return the cached status of all pods across all nodes"""
    with cached_status_lock:
        return jsonify(cached_status)

@app.route('/heartbeat', methods=['POST'])
def receive_heartbeat():
    """Receive heartbeat from a node"""
    data = request.json
    node_id = data.get('node_id')
    pod_health = data.get('pod_health', {})
    
    if not node_id:
        return jsonify({"status": "error", "message": "Missing node_id"}), 400
    
    with nodes_lock:
        if node_id in nodes:
            nodes[node_id]["last_heartbeat"] = time.time()
            nodes[node_id]["pod_health"] = pod_health
            return jsonify({"status": "success"})
        else:
            return jsonify({"status": "error", "message": "Unknown node"}), 404

@app.route('/list-nodes', methods=['GET'])
def list_nodes():
    """List all nodes with their status and pod health"""
    current_time = time.time()
    node_list = []
    
    with nodes_lock:
        for node_id, node_data in nodes.items():
            last_heartbeat = node_data["last_heartbeat"]
            healthy = (current_time - last_heartbeat) < 10  # Timeout after 10s
            
            node_list.append({
                "node_id": node_id,
                "healthy": healthy,
                "pod_health": node_data["pod_health"],
                "last_heartbeat": int(current_time - last_heartbeat),
                "capacity": node_data.get("capacity", DEFAULT_NODE_CAPACITY)  # Include capacity
            })
    
    return jsonify(node_list)

@app.route('/delete-pod', methods=['DELETE'])
def delete_pod():
    """Delete a pod from a node"""
    data = request.json
    node_id = data.get('node_id')
    pod_id = data.get('pod_id')
    
    if not node_id or not pod_id:
        return jsonify({"status": "error", "message": "Missing node_id or pod_id"}), 400
    
    try:
        # Get container IP address instead of using hostname
        with nodes_lock:
            if node_id not in nodes:
                return jsonify({"status": "error", "message": f"Node {node_id} not found"}), 404
                
            container = nodes[node_id]["container"]
            container_info = docker_client.api.inspect_container(container.id)
            container_ip = container_info['NetworkSettings']['Networks']['cluster-net']['IPAddress']
        
        response = requests.delete(
            f"http://{container_ip}:5001/delete-pod",
            json={"pod_id": pod_id},
            timeout=5
        )
        
        if response.status_code == 200:
            return jsonify({"status": "success"})
        else:
            return jsonify({"status": "error", "message": f"Node error: {response.text}"}), 400
    
    except requests.exceptions.RequestException as e:
        return jsonify({"status": "error", "message": f"Cannot reach node: {str(e)}"}), 500

@app.route('/delete-node', methods=['DELETE'])
def delete_node():
    """Delete a node from the cluster"""
    data = request.json
    node_id = data.get('node_id')
    
    if not node_id:
        return jsonify({"status": "error", "message": "Missing node_id"}), 400
    
    try:
        result, failed_reschedules = remove_node(node_id)
        
        response_data = {
            "status": "success",
            "message": f"Node {node_id} successfully removed"
        }
        
        if failed_reschedules:
            response_data["failed_reschedules"] = failed_reschedules
            response_data["message"] += f" but {len(failed_reschedules)} pods could not be rescheduled"
        else:
            response_data["message"] += " and all pods rescheduled successfully"
            
        return jsonify(response_data)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Unexpected error: {str(e)}"}), 500

def reschedule_pod(pod_id, cpu_request):
    """Reschedule a pod after its node has been deleted"""
    # Check if we have any nodes
    with nodes_lock:
        if not nodes:
            if AUTO_SCALE:
                # Add a node if auto-scaling is enabled
                print(f"No nodes available for rescheduling. Auto-creating a node for pod {pod_id}")
                response = add_node(auto_scaled=True)
                if isinstance(response, tuple) and len(response) > 1:
                    # Error occurred
                    print(f"Failed to create new node for rescheduling: {response[1]}")
                    return False
                
                # Allow some time for the node to start
                time.sleep(2)
            else:
                print(f"No nodes available for rescheduling, and auto-scaling is disabled")
                return False
    
    # Get current CPU allocation for each node
    with nodes_lock:
        node_allocations = {}
        for node_id, node_data in nodes.items():
            node_capacity = node_data.get("capacity", DEFAULT_NODE_CAPACITY)
            
            # Get all pods on this node and sum their CPU requests
            node_pods = {}
            with cached_status_lock:
                node_pods = cached_status.get(node_id, {})
            
            # Calculate total CPU requests for this node
            total_cpu_requests = sum(pod.get("cpu_request", 0) for pod in node_pods.values())
            
            # Store allocation data
            node_allocations[node_id] = {
                "allocated": total_cpu_requests,
                "capacity": node_capacity,
                "available": node_capacity - total_cpu_requests
            }
            
            print(f"Node {node_id}: {total_cpu_requests}/{node_capacity} cores allocated, {node_capacity - total_cpu_requests} available")
    
    # Find a suitable node based on scheduling algorithm
    target_node = None
    
    if SCHEDULING_ALGO == "first-fit":
        # First node with enough capacity
        for node_id, alloc_data in node_allocations.items():
            if alloc_data["available"] >= cpu_request:
                target_node = node_id
                print(f"Found suitable node {node_id} with {alloc_data['available']} cores available for rescheduled pod {pod_id}")
                break
    
    elif SCHEDULING_ALGO == "best-fit":
        # Node with smallest remaining capacity after adding the pod
        best_fit = None
        smallest_remaining = float('inf')
        
        for node_id, alloc_data in node_allocations.items():
            if alloc_data["available"] >= cpu_request:
                remaining = alloc_data["available"] - cpu_request
                if remaining < smallest_remaining:
                    smallest_remaining = remaining
                    best_fit = node_id
        
        target_node = best_fit
    
    elif SCHEDULING_ALGO == "worst-fit":
        # Node with most remaining capacity after adding the pod
        worst_fit = None
        largest_remaining = -1
        
        for node_id, alloc_data in node_allocations.items():
            if alloc_data["available"] >= cpu_request:
                remaining = alloc_data["available"] - cpu_request
                if remaining > largest_remaining:
                    largest_remaining = remaining
                    worst_fit = node_id
        
        target_node = worst_fit
    
    # If no node has capacity, add a new one if auto-scaling is enabled
    if target_node is None:
        if AUTO_SCALE:
            # Create a new node with enough capacity for this pod
            print(f"No node with sufficient capacity for rescheduled pod {pod_id}. Auto-creating a new node.")
            response = add_node(auto_scaled=True)
            if isinstance(response, tuple) and len(response) > 1:
                # Error occurred
                print(f"Failed to create new node for rescheduling: {response[1]}")
                return False
                
            node_data = response.get_json()
            target_node = node_data.get("node_id")
            
            # Allow some time for the node to start
            time.sleep(2)
        else:
            print(f"No node with sufficient capacity for rescheduled pod {pod_id}, and auto-scaling is disabled")
            return False
    
    # Send the pod to the target node
    try:
        # Check container is running first
        with nodes_lock:
            if target_node not in nodes:
                print(f"Target node {target_node} not found")
                return False
            
            container = nodes[target_node]["container"]
        
        print(f"Attempting to launch rescheduled pod {pod_id} on node {target_node} with {cpu_request} CPU cores")
        
        # Multiple attempts with exponential backoff
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                # Get container IP address instead of using hostname
                with nodes_lock:
                    container = nodes[target_node]["container"]
                    container_info = docker_client.api.inspect_container(container.id)
                    container_ip = container_info['NetworkSettings']['Networks']['cluster-net']['IPAddress']
                
                response = requests.post(
                    f"http://{container_ip}:5001/add-pod",
                    json={"pod_id": pod_id, "cpu_request": cpu_request},
                    timeout=5
                )
                
                if response.status_code == 200:
                    print(f"Successfully rescheduled pod {pod_id} on node {target_node}")
                    
                    # Update node allocations with the new pod's CPU request
                    with nodes_lock:
                        if target_node in node_allocations:
                            node_allocations[target_node]['allocated'] += cpu_request
                            node_allocations[target_node]['available'] -= cpu_request
                    
                    # Also update cached_status to include the new pod
                    with cached_status_lock:
                        if target_node not in cached_status:
                            cached_status[target_node] = {}
                        
                        cached_status[target_node][pod_id] = {
                            'cpu_request': cpu_request,
                            'cpu_usage': 0,  # Initial usage is 0
                            'healthy': True
                        }
                    
                    return True
                else:
                    print(f"Rescheduling attempt {attempt}/{max_attempts}: Node error: {response.text}")
                    if attempt == max_attempts:
                        return False
            except requests.exceptions.RequestException as e:
                print(f"Rescheduling attempt {attempt}/{max_attempts}: Cannot reach node: {str(e)}")
                if attempt == max_attempts:
                    return False
            
            # Exponential backoff
            if attempt < max_attempts:
                backoff_time = 2 ** (attempt - 1)
                print(f"Retrying rescheduling in {backoff_time} seconds...")
                time.sleep(backoff_time)
        
        return False
    
    except Exception as e:
        print(f"Unexpected error rescheduling pod: {str(e)}")
        return False

# Start metrics polling thread
metrics_thread = threading.Thread(target=poll_metrics, daemon=True)
metrics_thread.start()

if __name__ == '__main__':
    # Create the bridge network if it doesn't exist
    try:
        networks = docker_client.networks.list(names=["cluster-net"])
        if not networks:
            docker_client.networks.create("cluster-net", driver="bridge")
            print("Created cluster-net network")
    except docker.errors.APIError as e:
        print(f"Error creating network: {e}")
    
    app.run(host='0.0.0.0', port=5000) 