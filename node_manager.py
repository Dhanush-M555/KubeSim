import os
import math
import time
import json
import random
import threading
import requests
import psutil
from flask import Flask, request, jsonify

app = Flask(__name__)

# Get node ID from environment variable
NODE_ID = os.environ.get('NODE_ID', 'node_unknown')

# Config defaults
HEAVENLY_RESTRICTION = True  
DEFAULT_NODE_CAPACITY = 4    

config_locations = [
    '/data/config.json', 
    '/app/config.json', 
    './config.json'       
]

config_loaded = False
for config_path in config_locations:
    try:
        with open(config_path, 'r') as config_file:
            config = json.load(config_file)
            HEAVENLY_RESTRICTION = config.get('HEAVENLY_RESTRICTION', True)  # Default to true
            DEFAULT_NODE_CAPACITY = config.get('DEFAULT_NODE_CAPACITY', 4)   # Default cores per node
            print(f"Successfully loaded config from {config_path}: HEAVENLY_RESTRICTION={HEAVENLY_RESTRICTION}, DEFAULT_NODE_CAPACITY={DEFAULT_NODE_CAPACITY}")
            config_loaded = True
            break
    except Exception as e:
        print(f"Could not load config file from {config_path}: {str(e)}")

if not config_loaded:
    print(f"Warning: Could not load any config file, using defaults: HEAVENLY_RESTRICTION={HEAVENLY_RESTRICTION}, DEFAULT_NODE_CAPACITY={DEFAULT_NODE_CAPACITY}")

# Track pods with their CPU requests and threads
pods = {}  # {pod_id: {"thread": thread, "cpu_request": value, "healthy": bool}}
pods_lock = threading.Lock()

# Global variable to store the API server URL
API_SERVER_URL = None

def find_api_server():
    """Find the API server URL by trying different addresses"""
    global API_SERVER_URL
    
    api_addresses = [
        "http://host.docker.internal:5000",
        "http://172.17.0.1:5000",           # Default Docker bridge network gateway
        "http://app:5000",                   # Service name if using Docker Compose
        "http://localhost:5000"              # Local testing
    ]
    
    # Try to find the host IP address if running in Docker
    host_ip = None
    try:
        with open('/etc/hosts', 'r') as f:
            for line in f:
                if 'host.docker.internal' in line:
                    host_ip = line.split()[0]
                    if host_ip:
                        api_addresses.insert(0, f"http://{host_ip}:5000")
                        break
    except Exception as e:
        print(f"Could not read /etc/hosts: {e}")
    
    # Try each address until we find one that works
    for addr in api_addresses:
        try:
            print(f"Testing API server at {addr}")
            response = requests.get(f"{addr}/list-nodes", timeout=2)
            if response.status_code == 200:
                API_SERVER_URL = addr
                print(f"Successfully connected to API server at {API_SERVER_URL}")
                return API_SERVER_URL
        except Exception as e:
            print(f"Could not connect to {addr}: {e}")
    
    print("WARNING: Could not find API server! Defaulting to http://host.docker.internal:5000")
    API_SERVER_URL = "http://host.docker.internal:5000"
    return API_SERVER_URL

def send_heartbeat():
    """Send heartbeat to the API server every 5 seconds"""
    global API_SERVER_URL
    
    # Find the API server URL if not already set
    if not API_SERVER_URL:
        find_api_server()
    
    while True:
        try:
            pod_health = {}
            with pods_lock:
                for pod_id, pod_data in pods.items():
                    # Check if thread is alive
                    pod_health[pod_id] = pod_data["thread"].is_alive() and pod_data["healthy"]
            
            # Send heartbeat to the API server
            response = requests.post(
                f"{API_SERVER_URL}/heartbeat",
                json={"node_id": NODE_ID, "pod_health": pod_health},
                timeout=5
            )
            
            if response.status_code != 200:
                print(f"Error sending heartbeat: {response.status_code} {response.text}")
        except Exception as e:
            print(f"Error sending heartbeat: {e}")
            # Try to find the API server again in case it changed
            find_api_server()
        
        time.sleep(5)

def pod_workload(pod_id, cpu_request):
    """Simulate pod workload by computing prime numbers"""
    try:
        # Simulate random pod crash (5% chance)
        if random.random() < 0.05:
            with pods_lock:
                if pod_id in pods:
                    pods[pod_id]["healthy"] = False
            print(f"Pod {pod_id} crashed!")
            return
        
        # Compute prime numbers up to n to simulate CPU load
        n = int(cpu_request * 1000000)
        
        # If HEAVENLY_RESTRICTION is true, ensure we never exceed the CPU request
        if HEAVENLY_RESTRICTION:
            # Use psutil to monitor and limit CPU usage
            process = psutil.Process()
            
            # Set CPU affinity to limit cores if supported by platform
            try:
                # Get the total number of CPUs available
                total_cpus = psutil.cpu_count(logical=True)
                
                # Calculate the number of CPUs to use based on cpu_request
                # This is a rough approximation
                cpus_to_use = max(1, min(total_cpus, int(cpu_request)))
                
                # Get the list of all CPU IDs and select a subset
                all_cpus = list(range(total_cpus))
                selected_cpus = all_cpus[:cpus_to_use]
                
                # Set CPU affinity
                process.cpu_affinity(selected_cpus)
                print(f"Pod {pod_id}: Restricted to {cpus_to_use} cores due to HEAVENLY_RESTRICTION")
            except Exception as e:
                print(f"Warning: Could not set CPU affinity for pod {pod_id}: {e}")
        
        while True:
            sieve = [True] * (n + 1)
            for i in range(2, int(n**0.5) + 1):
                if sieve[i]:
                    for j in range(i*i, n + 1, i):
                        sieve[j] = False
            
            # Sleep to prevent 100% CPU usage on real host
            time.sleep(0.1)
            
            # Check if we should exit
            with pods_lock:
                if pod_id not in pods or not pods[pod_id]["healthy"]:
                    break
    except Exception as e:
        print(f"Error in pod workload {pod_id}: {e}")
        with pods_lock:
            if pod_id in pods:
                pods[pod_id]["healthy"] = False

@app.route('/add-pod', methods=['POST'])
def add_pod():
    """Add a new pod to this node"""
    data = request.json
    pod_id = data.get('pod_id')
    cpu_request = data.get('cpu_request', 1)
    
    if not pod_id:
        return jsonify({"status": "error", "message": "Missing pod_id"}), 400
    
    if not isinstance(cpu_request, (int, float)) or cpu_request <= 0:
        return jsonify({"status": "error", "message": "Invalid CPU request"}), 400
    
    # Get node capacity from environment variable
    node_capacity = int(os.environ.get('NODE_CAPACITY', DEFAULT_NODE_CAPACITY))
    
    # Check if we have enough capacity for this pod
    with pods_lock:
        # Calculate total CPU requests for existing pods
        total_allocated = sum(pod_data["cpu_request"] for pod_data in pods.values())
        
        # Check if adding this pod would exceed the node's capacity
        if total_allocated + cpu_request > node_capacity:
            print(f"REJECTING pod {pod_id} with CPU request {cpu_request}: Node capacity is {node_capacity}, " 
                  f"already allocated {total_allocated}, would exceed by {total_allocated + cpu_request - node_capacity}")
            return jsonify({
                "status": "error", 
                "message": f"Not enough capacity on node: {total_allocated}/{node_capacity} already allocated, " 
                           f"request is for {cpu_request}"
            }), 400
        
        print(f"ACCEPTING pod {pod_id} with CPU request {cpu_request}: " 
              f"Node capacity is {node_capacity}, already allocated {total_allocated}, " 
              f"will have {node_capacity - (total_allocated + cpu_request)} remaining")
    
    # Start a new thread for the pod
    thread = threading.Thread(
        target=pod_workload,
        args=(pod_id, cpu_request),
        daemon=True
    )
    thread.start()
    
    # Record the pod
    with pods_lock:
        pods[pod_id] = {
            "thread": thread,
            "cpu_request": cpu_request,
            "healthy": True
        }
    
    return jsonify({"status": "success", "pod_id": pod_id})

@app.route('/delete-pod', methods=['DELETE'])
def delete_pod():
    """Delete a pod from this node"""
    data = request.json
    pod_id = data.get('pod_id')
    
    if not pod_id:
        return jsonify({"status": "error", "message": "Missing pod_id"}), 400
    
    with pods_lock:
        if pod_id in pods:
            pods[pod_id]["healthy"] = False
            # Thread will terminate on its own
            del pods[pod_id]
            return jsonify({"status": "success"})
        else:
            return jsonify({"status": "error", "message": "Pod not found"}), 404

@app.route('/metrics', methods=['GET'])
def metrics():
    """Return CPU usage metrics for all pods"""
    node_cpu_percent = psutil.cpu_percent(interval=0.1)
    
    # Get the number of logical CPUs on the host
    cpu_count = psutil.cpu_count(logical=True)
    
    # Calculate total CPU request
    total_request = 0
    metrics_data = {}
    
    with pods_lock:
        for pod_id, pod_data in pods.items():
            total_request += pod_data["cpu_request"]
        
        # If no pods, return empty metrics
        if not pods:
            return jsonify({})
        
        # Distribute the node CPU usage proportionally to each pod's request
        for pod_id, pod_data in pods.items():
            # Calculate pod's share of CPU
            pod_share = pod_data["cpu_request"] / total_request if total_request > 0 else 0
            
            # Calculate CPU usage for this pod
            pod_cpu_usage = node_cpu_percent * pod_share * cpu_count / 100
            
            # Check if Heavenly Restriction is enabled
            if HEAVENLY_RESTRICTION:
                # Strictly enforce the CPU request as the maximum - no exceptions
                pod_cpu_usage = min(pod_cpu_usage, pod_data["cpu_request"])
                
                # Remove any fluctuations or randomness in restricted mode
                # Ensure it never exceeds the requested amount
                metrics_data[pod_id] = {
                    "cpu_usage": pod_cpu_usage,
                    "cpu_request": pod_data["cpu_request"],
                    "restricted": True
                }
            else:
                # Add random fluctuation to make it more realistic (allow exceeding limit)
                # This simulates real-world where containers can temporarily use more than their limit
                fluctuation = random.uniform(0.8, 1.2)
                pod_cpu_usage *= fluctuation
                
                # Sometimes allow exceeding the limit to simulate real-world behavior
                if random.random() > 0.7:  # 30% chance to exceed
                    # Allow exceeding by up to 20%
                    max_exceed = pod_data["cpu_request"] * 1.2
                    pod_cpu_usage = min(pod_cpu_usage, max_exceed)
                else:
                    # Otherwise respect the limit
                    pod_cpu_usage = min(pod_cpu_usage, pod_data["cpu_request"])
                
                metrics_data[pod_id] = {
                    "cpu_usage": pod_cpu_usage,
                    "cpu_request": pod_data["cpu_request"],
                    "restricted": False
                }
    
    # Add node info to response
    metrics_data["_node_info"] = {
        "heavenly_restriction": HEAVENLY_RESTRICTION,
        "node_capacity": int(os.environ.get('NODE_CAPACITY', DEFAULT_NODE_CAPACITY)),
        "config_loaded": config_loaded
    }
    
    return jsonify(metrics_data)

# Start heartbeat thread
heartbeat_thread = threading.Thread(target=send_heartbeat, daemon=True)
heartbeat_thread.start()

if __name__ == '__main__':
    # Run the Flask application
    app.run(host='0.0.0.0', port=5001)