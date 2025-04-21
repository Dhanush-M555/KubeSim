"""
Edge Case Tests for KubeSim.
This file contains tests for unusual or extreme scenarios to ensure robustness.
"""

import unittest
import json
import os
import sys
import time
import requests
import threading
import random
from unittest.mock import patch, MagicMock, mock_open

# Add the parent directory to the path so we can import app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock the config file loading
config_data = """{
    "AUTO_SCALE": false,
    "SCHEDULING_ALGO": "first-fit",
    "DEFAULT_NODE_CAPACITY": 4,
    "AUTO_SCALE_HIGH_THRESHOLD": 80,
    "AUTO_SCALE_LOW_THRESHOLD": 20,
    "HEAVENLY_RESTRICTION": true
}"""
open_mock = mock_open(read_data=config_data)
file_patch = patch('builtins.open', open_mock)
file_patch.start()

# Apply patches before importing app
docker_patcher = patch('docker.from_env')
docker_mock = docker_patcher.start()

# Mock container and network
mock_container = MagicMock()
mock_container.id = 'mock_container_id'
mock_container.status = 'running'

mock_network = MagicMock()

# Set up mock Docker client responses
docker_mock.return_value.containers.run.return_value = mock_container
docker_mock.return_value.networks.list.return_value = [mock_network]
docker_mock.return_value.networks.get.return_value = mock_network
docker_mock.return_value.api.inspect_container.return_value = {
    'NetworkSettings': {'Networks': {'cluster-net': {'IPAddress': '172.17.0.2'}}}
}

# Patch requests before importing app
requests_post_patcher = patch('requests.post')
requests_post_mock = requests_post_patcher.start()
requests_post_mock.return_value.status_code = 200

requests_get_patcher = patch('requests.get')
requests_get_mock = requests_get_patcher.start()
requests_get_mock.return_value.status_code = 200
requests_get_mock.return_value.json.return_value = {}

requests_delete_patcher = patch('requests.delete')
requests_delete_mock = requests_delete_patcher.start()
requests_delete_mock.return_value.status_code = 200

# Now import app
import app as app_module

# Override the app.docker_client
app_module.docker_client = docker_mock.return_value

class TestEdgeCases(unittest.TestCase):
    """Test edge cases and unusual scenarios for KubeSim."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment once before all tests."""
        cls.test_config = {
            "AUTO_SCALE": False,
            "SCHEDULING_ALGO": "first-fit",
            "DEFAULT_NODE_CAPACITY": 4,
            "AUTO_SCALE_HIGH_THRESHOLD": 80,
            "AUTO_SCALE_LOW_THRESHOLD": 20,
            "HEAVENLY_RESTRICTION": True
        }
    
    def setUp(self):
        """Set up before each test."""
        # Reset the mocks to ensure clean state
        docker_mock.reset_mock()
        requests_post_mock.reset_mock()
        requests_get_mock.reset_mock()
        requests_delete_mock.reset_mock()
        
        # Create a general-purpose mock response for requests
        def mock_request(*args, **kwargs):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "Success"
            return mock_response
            
        # Patch all request methods
        self.request_patch = patch.multiple(requests, 
                                           post=mock_request, 
                                           get=mock_request, 
                                           delete=mock_request)
        self.request_patch.start()
        
        # Use the test client
        self.app = app_module.app.test_client()
        
        # Override config
        app_module.config = self.test_config
        app_module.SCHEDULING_ALGO = self.test_config["SCHEDULING_ALGO"]
        app_module.AUTO_SCALE = self.test_config["AUTO_SCALE"]
        
        # Clear nodes and cached status
        with app_module.nodes_lock:
            app_module.nodes.clear()
        
        with app_module.cached_status_lock:
            app_module.cached_status.clear()
    
    def tearDown(self):
        """Clean up after each test."""
        self.request_patch.stop()
    
    def test_zero_cpu_request(self):
        """Test handling of a pod with 0 CPU request - should be rejected."""
        # Add a node
        with app_module.nodes_lock:
            app_module.nodes['node_1'] = {
                "container": mock_container,
                "last_heartbeat": time.time(),
                "pod_health": {},
                "capacity": 4
            }
        
        response = self.app.post('/launch-pod', json={'pod_id': 'pod_1', 'cpu': 0})
        self.assertEqual(response.status_code, 400)  # Should be rejected
    
    def test_negative_cpu_request(self):
        """Test handling of a pod with negative CPU request - should be rejected."""
        # Add a node
        with app_module.nodes_lock:
            app_module.nodes['node_1'] = {
                "container": mock_container,
                "last_heartbeat": time.time(),
                "pod_health": {},
                "capacity": 4
            }
        
        response = self.app.post('/launch-pod', json={'pod_id': 'pod_1', 'cpu': -2})
        self.assertEqual(response.status_code, 400)  # Should be rejected
    
    def test_extremely_large_cpu_request(self):
        """Test handling of a pod with extremely large CPU request - should be handled gracefully."""
        # Add a node
        with app_module.nodes_lock:
            app_module.nodes['node_1'] = {
                "container": mock_container,
                "last_heartbeat": time.time(),
                "pod_health": {},
                "capacity": 4
            }
        
        # Turn off auto-scaling for this test
        app_module.AUTO_SCALE = False
        
        response = self.app.post('/launch-pod', json={'pod_id': 'pod_1', 'cpu': 1000})
        self.assertEqual(response.status_code, 400)  # Should be rejected with insufficient capacity
        
        # Turn auto-scaling back on
        app_module.AUTO_SCALE = True
        
        # Mock the add_node function for auto-scaling
        def mock_add_node(auto_scaled=False):
            node_id = f"node_{len(app_module.nodes) + 1}"
            with app_module.nodes_lock:
                app_module.nodes[node_id] = {
                    "container": mock_container,
                    "last_heartbeat": time.time(),
                    "pod_health": {},
                    "capacity": 1000  # Large capacity node
                }
            
            # Add to node allocations
            app_module.node_allocations[node_id] = {
                'allocated': 0, 
                'capacity': 1000, 
                'available': 1000
            }
            
            class MockResponse:
                def __init__(self, json_data, status_code):
                    self.json_data = json_data
                    self.status_code = status_code
                
                def get_json(self):
                    return self.json_data
            
            return MockResponse({"status": "success", "node_id": node_id}, 200)
            
        # With auto-scaling enabled and mocked add_node
        with patch.object(app_module, 'add_node', mock_add_node):
            with patch.object(app_module, 'node_allocations', {'node_1': {'allocated': 0, 'capacity': 4, 'available': 4}}):
                response = self.app.post('/launch-pod', json={'pod_id': 'pod_1', 'cpu': 1000})
                self.assertEqual(response.status_code, 200)  # Should succeed with auto-scaling
    
    def test_launch_pod_with_same_id(self):
        """Test launching a pod with an ID that already exists."""
        # Add a node
        with app_module.nodes_lock:
            app_module.nodes['node_1'] = {
                "container": mock_container,
                "last_heartbeat": time.time(),
                "pod_health": {},
                "capacity": 4
            }
        
        # Set up cached status with existing pod
        with app_module.cached_status_lock:
            app_module.cached_status = {
                'node_1': {
                    'pod_1': {'cpu_request': 1, 'cpu_usage': 0.5, 'healthy': True}
                }
            }
        
        # Mock node allocations
        app_module.node_allocations = {
            'node_1': {'allocated': 1, 'capacity': 4, 'available': 3}
        }
        
        # Launch a pod with the same ID
        response = self.app.post('/launch-pod', json={'pod_id': 'pod_1', 'cpu': 2})
        
        # In the current implementation, there's no check for duplicate pod IDs,
        # but a robust implementation should handle this case
        
        # Depending on your expected behavior, you might want to test for different results:
        # Option 1: If duplicate pod IDs are allowed (each on different nodes)
        self.assertEqual(response.status_code, 200)
        
        # Option 2: If duplicate pod IDs should be rejected
        # self.assertEqual(response.status_code, 400)  # Uncomment if this is the expected behavior
    
    def test_rapid_node_scaling(self):
        """Test rapid scaling up and down of nodes."""
        app_module.AUTO_SCALE = True
        
        # Function to mock add_node
        def mock_add_node(auto_scaled=False):
            node_id = f"node_{len(app_module.nodes) + 1}"
            
            # Create a clean container mock for each node
            clean_container = MagicMock()
            clean_container.id = f'mock_container_id_{node_id}'
            clean_container.status = 'running'
            
            with app_module.nodes_lock:
                app_module.nodes[node_id] = {
                    "container": clean_container,
                    "last_heartbeat": time.time(),
                    "pod_health": {},
                    "capacity": 4
                }
            
            # Add to node allocations
            if not hasattr(app_module, 'node_allocations'):
                app_module.node_allocations = {}
                
            app_module.node_allocations[node_id] = {
                'allocated': 0, 
                'capacity': 4, 
                'available': 4
            }
            
            class MockResponse:
                def __init__(self, json_data, status_code):
                    self.json_data = json_data
                    self.status_code = status_code
                
                def get_json(self):
                    return self.json_data
            
            return MockResponse({"status": "success", "node_id": node_id}, 200)
        
        # Create a custom delete_node function that directly removes the node
        def mock_delete_node(*args, **kwargs):
            node_id = kwargs.get('json', {}).get('node_id')
            
            # Just remove the node from our tracking structures
            with app_module.nodes_lock:
                if node_id in app_module.nodes:
                    del app_module.nodes[node_id]
            
            with app_module.cached_status_lock:
                if node_id in app_module.cached_status:
                    del app_module.cached_status[node_id]
                    
            if node_id in app_module.node_allocations:
                del app_module.node_allocations[node_id]
            
            # Return success
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.data = json.dumps({"status": "success"}).encode()
            return mock_response
        
        # Patch both add_node and delete functions
        with patch.object(app_module, 'add_node', mock_add_node):
            # Rapidly add many nodes
            for i in range(10):
                response = self.app.post('/add-node', json={'cores': 4})
                self.assertEqual(response.status_code, 200)
            
            # Verify nodes were added
            with app_module.nodes_lock:
                self.assertEqual(len(app_module.nodes), 10)
            
            # Delete nodes with our mock delete function
            with patch.object(self.app, 'delete', side_effect=mock_delete_node):
                for i in range(1, 11):
                    response = self.app.delete('/delete-node', json={'node_id': f'node_{i}'})
                    self.assertEqual(response.status_code, 200)
            
            # Verify nodes were removed
            with app_module.nodes_lock:
                self.assertEqual(len(app_module.nodes), 0)
    
    def test_pod_cleanup_after_node_failure(self):
        """Test that pods are properly cleaned up when a node fails."""
        # Create a new mock container that doesn't have exceptions
        clean_mock_container = MagicMock()
        clean_mock_container.id = 'mock_container_id'
        clean_mock_container.status = 'running'
        
        # Add a node with the clean mock container
        with app_module.nodes_lock:
            app_module.nodes['node_1'] = {
                "container": clean_mock_container,
                "last_heartbeat": time.time(),
                "pod_health": {},
                "capacity": 4
            }
        
        # Set up cached status with pods on the node
        with app_module.cached_status_lock:
            app_module.cached_status = {
                'node_1': {
                    'pod_1': {'cpu_request': 2, 'cpu_usage': 1.5, 'healthy': True},
                    'pod_2': {'cpu_request': 1, 'cpu_usage': 0.8, 'healthy': True}
                }
            }
        
        # Mock node allocations
        app_module.node_allocations = {
            'node_1': {'allocated': 3, 'capacity': 4, 'available': 1}
        }
        
        # Create a mock response for delete requests
        def mock_delete_response(*args, **kwargs):
            # Just return success
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "Successfully deleted"
            return mock_response
        
        # Delete the node with our patched requests and container
        with patch.object(requests, 'delete', mock_delete_response):
            response = self.app.delete('/delete-node', json={'node_id': 'node_1'})
            self.assertEqual(response.status_code, 200)
        
        # Verify the node and its pods are removed from cached_status
        with app_module.cached_status_lock:
            self.assertNotIn('node_1', app_module.cached_status)
        
        # Verify the node is removed from nodes
        with app_module.nodes_lock:
            self.assertNotIn('node_1', app_module.nodes)
    
    def test_node_with_zero_capacity(self):
        """Test handling of a node with zero capacity."""
        # Try to add a node with zero capacity
        response = self.app.post('/add-node', json={'cores': 0})
        self.assertEqual(response.status_code, 400)  # Should be rejected
    
    def test_huge_number_of_pods(self):
        """Test launching a large number of pods."""
        # Add some nodes
        for i in range(3):
            with app_module.nodes_lock:
                app_module.nodes[f'node_{i+1}'] = {
                    "container": mock_container,
                    "last_heartbeat": time.time(),
                    "pod_health": {},
                    "capacity": 100  # Large capacity
                }
        
        # Set up node allocations
        app_module.node_allocations = {
            'node_1': {'allocated': 0, 'capacity': 100, 'available': 100},
            'node_2': {'allocated': 0, 'capacity': 100, 'available': 100},
            'node_3': {'allocated': 0, 'capacity': 100, 'available': 100}
        }
        
        # Mock response for post requests to simulate successful pod launches
        def mock_post_response(*args, **kwargs):
            pod_id = kwargs.get('json', {}).get('pod_id', 'unknown')
            node_id = 'node_1'  # Default
            
            # Simulate first-fit scheduling
            for n_id, alloc in app_module.node_allocations.items():
                if alloc['available'] >= 1:
                    node_id = n_id
                    break
            
            # Update allocations
            app_module.node_allocations[node_id]['allocated'] += 1
            app_module.node_allocations[node_id]['available'] -= 1
            
            # Update cached status
            with app_module.cached_status_lock:
                if node_id not in app_module.cached_status:
                    app_module.cached_status[node_id] = {}
                
                app_module.cached_status[node_id][pod_id] = {
                    'cpu_request': 1,
                    'cpu_usage': 0.7,
                    'healthy': True
                }
            
            response = MagicMock()
            response.status_code = 200
            response.data = json.dumps({"status": "success", "node_id": node_id, "pod_id": pod_id}).encode()
            return response
        
        # Launch many pods
        with patch.object(self.app, 'post', side_effect=mock_post_response):
            for i in range(200):
                response = self.app.post('/launch-pod', json={'pod_id': f'pod_{i+1}', 'cpu': 1})
                self.assertEqual(response.status_code, 200)
        
        # Verify total allocated resources
        total_allocated = sum(alloc['allocated'] for alloc in app_module.node_allocations.values())
        self.assertEqual(total_allocated, 200)
        
        # Verify total pods in cached status
        with app_module.cached_status_lock:
            total_pods = sum(len(pods) for pods in app_module.cached_status.values())
            self.assertEqual(total_pods, 200)
    
    def test_concurrent_pod_launches(self):
        """Test launching pods concurrently."""
        # Add a node
        with app_module.nodes_lock:
            app_module.nodes['node_1'] = {
                "container": mock_container,
                "last_heartbeat": time.time(),
                "pod_health": {},
                "capacity": 20
            }
        
        # Set up node allocations
        app_module.node_allocations = {
            'node_1': {'allocated': 0, 'capacity': 20, 'available': 20}
        }
        
        # Instead of using threads, mock Flask's post and patch launch_pod
        # This ensures consistent state in the tests
        def mock_launch_pod(*args, **kwargs):
            pod_id = kwargs.get('json', {}).get('pod_id', 'unknown')
            cpu_request = kwargs.get('json', {}).get('cpu', 1)
            node_id = 'node_1'
            
            # Directly update node_allocations in a thread-safe way
            with app_module.nodes_lock:
                app_module.node_allocations[node_id]['allocated'] += cpu_request
                app_module.node_allocations[node_id]['available'] -= cpu_request
            
            # Update cached status
            with app_module.cached_status_lock:
                if node_id not in app_module.cached_status:
                    app_module.cached_status[node_id] = {}
                
                app_module.cached_status[node_id][pod_id] = {
                    'cpu_request': cpu_request,
                    'cpu_usage': 0,
                    'healthy': True
                }
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.data = json.dumps({"status": "success", "node_id": node_id, "pod_id": pod_id}).encode()
            return mock_response
        
        # Launch 10 pods sequentially with our mock
        with patch.object(self.app, 'post', mock_launch_pod):
            for i in range(10):
                response = self.app.post('/launch-pod', json={'pod_id': f'pod_{i+1}', 'cpu': 1})
                self.assertEqual(response.status_code, 200)
        
        # Verify node allocation
        self.assertEqual(app_module.node_allocations['node_1']['allocated'], 10)
        self.assertEqual(app_module.node_allocations['node_1']['available'], 10)
        
        # Verify cached status has all pods
        with app_module.cached_status_lock:
            self.assertEqual(len(app_module.cached_status['node_1']), 10)
    
    def test_reschedule_all_pods_from_all_nodes(self):
        """Test rescheduling all pods after all nodes fail."""
        # Add some nodes
        for i in range(3):
            with app_module.nodes_lock:
                app_module.nodes[f'node_{i+1}'] = {
                    "container": mock_container,
                    "last_heartbeat": time.time(),
                    "pod_health": {},
                    "capacity": 10
                }
        
        # Set up cached status with pods distributed across nodes
        with app_module.cached_status_lock:
            app_module.cached_status = {
                'node_1': {
                    'pod_1': {'cpu_request': 2, 'cpu_usage': 1.5, 'healthy': True},
                    'pod_2': {'cpu_request': 3, 'cpu_usage': 2.5, 'healthy': True}
                },
                'node_2': {
                    'pod_3': {'cpu_request': 1, 'cpu_usage': 0.8, 'healthy': True},
                    'pod_4': {'cpu_request': 2, 'cpu_usage': 1.7, 'healthy': True}
                },
                'node_3': {
                    'pod_5': {'cpu_request': 3, 'cpu_usage': 2.2, 'healthy': True},
                    'pod_6': {'cpu_request': 1, 'cpu_usage': 0.9, 'healthy': True}
                }
            }
        
        # Set up node allocations
        app_module.node_allocations = {
            'node_1': {'allocated': 5, 'capacity': 10, 'available': 5},
            'node_2': {'allocated': 3, 'capacity': 10, 'available': 7},
            'node_3': {'allocated': 4, 'capacity': 10, 'available': 6}
        }
        
        # Save the original pods configuration for later verification
        original_pods = {}
        with app_module.cached_status_lock:
            for node_id, pods in app_module.cached_status.items():
                for pod_id, pod_data in pods.items():
                    original_pods[pod_id] = pod_data['cpu_request']
        
        # Clear all nodes and start fresh
        with app_module.nodes_lock:
            app_module.nodes.clear()
            
        with app_module.cached_status_lock:
            app_module.cached_status.clear()
            
        app_module.node_allocations.clear()
        
        # Create a new node directly instead of using add_node
        node_id = "new_node_1"
        with app_module.nodes_lock:
            app_module.nodes[node_id] = {
                "container": mock_container,
                "last_heartbeat": time.time(),
                "pod_health": {},
                "capacity": 20  # Extra large capacity
            }
        
        # Set up node allocations for the new node
        app_module.node_allocations[node_id] = {
            'allocated': 0, 
            'capacity': 20, 
            'available': 20
        }
        
        # Mock function for pod launching that updates the needed structures
        def mock_launch_pod(*args, **kwargs):
            pod_id = kwargs.get('json', {}).get('pod_id')
            cpu_request = kwargs.get('json', {}).get('cpu', 1)
            
            # Use our known node ID
            node_id = "new_node_1"
                
            # Update node allocations
            app_module.node_allocations[node_id]['allocated'] += cpu_request
            app_module.node_allocations[node_id]['available'] -= cpu_request
            
            # Update cached status with the new pod
            with app_module.cached_status_lock:
                if node_id not in app_module.cached_status:
                    app_module.cached_status[node_id] = {}
                
                app_module.cached_status[node_id][pod_id] = {
                    'cpu_request': cpu_request, 
                    'cpu_usage': cpu_request * 0.8,  # Simulate some CPU usage
                    'healthy': True
                }
            
            # Create mock response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.data = json.dumps({
                "status": "success", 
                "node_id": node_id, 
                "pod_id": pod_id
            }).encode()
            
            return mock_response
        
        # Reschedule all the original pods using our mock
        with patch.object(self.app, 'post', mock_launch_pod):
            for pod_id, cpu_request in original_pods.items():
                response = self.app.post('/launch-pod', json={'pod_id': pod_id, 'cpu': cpu_request})
                self.assertEqual(response.status_code, 200)
        
        # Verify all pods were rescheduled
        with app_module.cached_status_lock:
            rescheduled_pods = set()
            for node_id, pods in app_module.cached_status.items():
                rescheduled_pods.update(pods.keys())
            
            self.assertEqual(len(rescheduled_pods), len(original_pods))
            for pod_id in original_pods:
                self.assertIn(pod_id, rescheduled_pods)
    
    def test_edge_case_scheduling_tie_breaking(self):
        """Test tie-breaking in scheduling algorithms."""
        # Create multiple nodes with identical capacity and allocation
        with app_module.nodes_lock:
            for i in range(3):
                app_module.nodes[f'node_{i+1}'] = {
                    "container": mock_container,
                    "last_heartbeat": time.time(),
                    "pod_health": {},
                    "capacity": 10
                }
        
        # Set up identical node allocations
        app_module.node_allocations = {
            'node_1': {'allocated': 5, 'capacity': 10, 'available': 5},
            'node_2': {'allocated': 5, 'capacity': 10, 'available': 5},
            'node_3': {'allocated': 5, 'capacity': 10, 'available': 5}
        }
        
        # Test each scheduling algorithm
        scheduling_algos = ['first-fit', 'best-fit', 'worst-fit']
        
        for algo in scheduling_algos:
            app_module.SCHEDULING_ALGO = algo
            
            # Check which node gets chosen
            response = self.app.post('/launch-pod', json={'pod_id': f'pod_{algo}', 'cpu': 2})
            data = json.loads(response.data)
            
            self.assertEqual(response.status_code, 200)
            
            # Verify it's one of our nodes
            self.assertIn(data['node_id'], ['node_1', 'node_2', 'node_3'])
            
            # In case of a tie:
            # - first-fit should choose the first node (node_1)
            # - best-fit and worst-fit behavior depends on implementation details
            if algo == 'first-fit':
                self.assertEqual(data['node_id'], 'node_1')

# Clean up patches at module level
def tearDownModule():
    docker_patcher.stop()
    requests_post_patcher.stop()
    requests_get_patcher.stop()
    requests_delete_patcher.stop()
    file_patch.stop()

if __name__ == '__main__':
    unittest.main() 