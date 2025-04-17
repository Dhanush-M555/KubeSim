"""
Tests for scheduling algorithms in KubeSim.
This tests first-fit, best-fit, and worst-fit scheduling algorithms.
"""

import unittest
import json
import os
import sys
import time
import requests
import threading
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

# Now import app
import app as app_module

# Override the app.docker_client
app_module.docker_client = docker_mock.return_value

class TestSchedulingAlgorithms(unittest.TestCase):
    """Test cases for scheduling algorithms in KubeSim."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment once before all tests."""
        # Create a test config
        cls.test_config = {
            "AUTO_SCALE": False,
            "SCHEDULING_ALGO": "first-fit",
            "DEFAULT_NODE_CAPACITY": 4,
            "AUTO_SCALE_HIGH_THRESHOLD": 80,
            "AUTO_SCALE_LOW_THRESHOLD": 20,
            "HEAVENLY_RESTRICTION": True
        }
        
        # No need to write config file now that we're mocking it
        # with open('test_config.json', 'w') as f:
        #     json.dump(cls.test_config, f)
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests are complete."""
        # No need to remove the config file
        # if os.path.exists('test_config.json'):
        #     os.remove('test_config.json')
        pass
    
    def setUp(self):
        """Set up before each test."""
        # Reset the mocks to ensure clean state
        docker_mock.reset_mock()
        requests_post_mock.reset_mock()
        requests_get_mock.reset_mock()
        
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
        pass
    
    def test_first_fit_scheduling(self):
        """Test the first-fit scheduling algorithm."""
        # Set the scheduling algorithm to first-fit
        app_module.SCHEDULING_ALGO = 'first-fit'
        
        # Mock the node allocations - this needs to be done after the node is added
        def mock_node_allocations(*args, **kwargs):
            # Add nodes to the system
            for i in range(3):
                node_id = f"node_{i+1}"
                with app_module.nodes_lock:
                    app_module.nodes[node_id] = {
                        "container": mock_container,
                        "last_heartbeat": time.time(),
                        "pod_health": {},
                        "capacity": 4
                    }
                    
            # Set up node allocations manually
            app_module.node_allocations = {
                'node_1': {'allocated': 2, 'capacity': 4, 'available': 2},
                'node_2': {'allocated': 1, 'capacity': 4, 'available': 3},
                'node_3': {'allocated': 3, 'capacity': 4, 'available': 1}
            }
            
            # Update cached status to match node allocations
            with app_module.cached_status_lock:
                app_module.cached_status = {
                    'node_1': {
                        'pod_1': {'cpu_request': 2, 'cpu_usage': 1.5, 'healthy': True}
                    },
                    'node_2': {
                        'pod_2': {'cpu_request': 1, 'cpu_usage': 0.8, 'healthy': True}
                    },
                    'node_3': {
                        'pod_3': {'cpu_request': 3, 'cpu_usage': 2.5, 'healthy': True}
                    }
                }
            
            return app_module.node_allocations
            
        # Create a custom mock for the post request to simulate a successful pod launch
        def mock_post(*args, **kwargs):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "Success"
            return mock_response
            
        # Use the mock functions
        with patch.object(app_module, 'node_allocations', mock_node_allocations()):
            with patch.object(requests, 'post', mock_post):
                # Launch a pod with 2 CPU request - should go to node_1 (first fit)
                response = self.app.post('/launch-pod', json={'pod_id': 'test_pod_1', 'cpu': 2})
                data = json.loads(response.data)
                
                self.assertEqual(response.status_code, 200)
                self.assertEqual(data['node_id'], 'node_1')
    
    def test_best_fit_scheduling(self):
        """Test the best-fit scheduling algorithm."""
        # Set the scheduling algorithm to best-fit
        app_module.SCHEDULING_ALGO = 'best-fit'
        
        # Mock the node allocations - this needs to be done after the node is added
        def mock_node_allocations(*args, **kwargs):
            # Add nodes to the system
            for i in range(3):
                node_id = f"node_{i+1}"
                with app_module.nodes_lock:
                    app_module.nodes[node_id] = {
                        "container": mock_container,
                        "last_heartbeat": time.time(),
                        "pod_health": {},
                        "capacity": 4
                    }
                    
            # Set up node allocations manually
            app_module.node_allocations = {
                'node_1': {'allocated': 2, 'capacity': 4, 'available': 2},
                'node_2': {'allocated': 1, 'capacity': 4, 'available': 3},
                'node_3': {'allocated': 3, 'capacity': 4, 'available': 1}
            }
            
            # Update cached status to match node allocations
            with app_module.cached_status_lock:
                app_module.cached_status = {
                    'node_1': {
                        'pod_1': {'cpu_request': 2, 'cpu_usage': 1.5, 'healthy': True}
                    },
                    'node_2': {
                        'pod_2': {'cpu_request': 1, 'cpu_usage': 0.8, 'healthy': True}
                    },
                    'node_3': {
                        'pod_3': {'cpu_request': 3, 'cpu_usage': 2.5, 'healthy': True}
                    }
                }
            
            return app_module.node_allocations
            
        # Create a custom mock for the post request to simulate a successful pod launch
        def mock_post(*args, **kwargs):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "Success"
            return mock_response
            
        # Use the mock functions
        with patch.object(app_module, 'node_allocations', mock_node_allocations()):
            with patch.object(requests, 'post', mock_post):
                # Launch a pod with 1 CPU request - should go to node_3 (best fit - smallest remaining capacity)
                response = self.app.post('/launch-pod', json={'pod_id': 'test_pod_1', 'cpu': 1})
                data = json.loads(response.data)
                
                self.assertEqual(response.status_code, 200)
                self.assertEqual(data['node_id'], 'node_3')
    
    def test_worst_fit_scheduling(self):
        """Test the worst-fit scheduling algorithm."""
        # Set the scheduling algorithm to worst-fit
        app_module.SCHEDULING_ALGO = 'worst-fit'
        
        # Mock the node allocations - this needs to be done after the node is added
        def mock_node_allocations(*args, **kwargs):
            # Add nodes to the system
            for i in range(3):
                node_id = f"node_{i+1}"
                with app_module.nodes_lock:
                    app_module.nodes[node_id] = {
                        "container": mock_container,
                        "last_heartbeat": time.time(),
                        "pod_health": {},
                        "capacity": 4
                    }
                    
            # Set up node allocations manually
            app_module.node_allocations = {
                'node_1': {'allocated': 2, 'capacity': 4, 'available': 2},
                'node_2': {'allocated': 1, 'capacity': 4, 'available': 3},
                'node_3': {'allocated': 3, 'capacity': 4, 'available': 1}
            }
            
            # Update cached status to match node allocations
            with app_module.cached_status_lock:
                app_module.cached_status = {
                    'node_1': {
                        'pod_1': {'cpu_request': 2, 'cpu_usage': 1.5, 'healthy': True}
                    },
                    'node_2': {
                        'pod_2': {'cpu_request': 1, 'cpu_usage': 0.8, 'healthy': True}
                    },
                    'node_3': {
                        'pod_3': {'cpu_request': 3, 'cpu_usage': 2.5, 'healthy': True}
                    }
                }
            
            return app_module.node_allocations
            
        # Create a custom mock for the post request to simulate a successful pod launch
        def mock_post(*args, **kwargs):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "Success"
            return mock_response
            
        # Use the mock functions
        with patch.object(app_module, 'node_allocations', mock_node_allocations()):
            with patch.object(requests, 'post', mock_post):
                # Launch a pod with 1 CPU request - should go to node_2 (worst fit - largest remaining capacity)
                response = self.app.post('/launch-pod', json={'pod_id': 'test_pod_1', 'cpu': 1})
                data = json.loads(response.data)
                
                self.assertEqual(response.status_code, 200)
                self.assertEqual(data['node_id'], 'node_2')
    
    def test_insufficient_capacity(self):
        """Test behavior when no node has enough capacity."""
        # Set the scheduling algorithm to first-fit
        app_module.SCHEDULING_ALGO = 'first-fit'
        app_module.AUTO_SCALE = False
        
        # Mock the node allocations - this needs to be done after the node is added
        def mock_node_allocations(*args, **kwargs):
            # Add nodes to the system
            for i in range(3):
                node_id = f"node_{i+1}"
                with app_module.nodes_lock:
                    app_module.nodes[node_id] = {
                        "container": mock_container,
                        "last_heartbeat": time.time(),
                        "pod_health": {},
                        "capacity": 4
                    }
                    
            # Set up node allocations manually - all nodes are full
            app_module.node_allocations = {
                'node_1': {'allocated': 4, 'capacity': 4, 'available': 0},
                'node_2': {'allocated': 4, 'capacity': 4, 'available': 0},
                'node_3': {'allocated': 4, 'capacity': 4, 'available': 0}
            }
            
            # Update cached status to match node allocations
            with app_module.cached_status_lock:
                app_module.cached_status = {
                    'node_1': {
                        'pod_1': {'cpu_request': 4, 'cpu_usage': 3.5, 'healthy': True}
                    },
                    'node_2': {
                        'pod_2': {'cpu_request': 4, 'cpu_usage': 3.8, 'healthy': True}
                    },
                    'node_3': {
                        'pod_3': {'cpu_request': 4, 'cpu_usage': 3.5, 'healthy': True}
                    }
                }
            
            return app_module.node_allocations
            
        # Use the mock function
        with patch.object(app_module, 'node_allocations', mock_node_allocations()):
            # Launch a pod with 2 CPU request - should fail
            response = self.app.post('/launch-pod', json={'pod_id': 'test_pod_1', 'cpu': 2})
            self.assertEqual(response.status_code, 400)  # Should return 400 Bad Request
    
    def test_autoscaling(self):
        """Test auto-scaling when no node has enough capacity."""
        # Set the scheduling algorithm to first-fit
        app_module.SCHEDULING_ALGO = 'first-fit'
        app_module.AUTO_SCALE = True
        
        # Mock the node allocations - this needs to be done after the node is added
        def mock_node_allocations(*args, **kwargs):
            # Add nodes to the system
            for i in range(3):
                node_id = f"node_{i+1}"
                with app_module.nodes_lock:
                    app_module.nodes[node_id] = {
                        "container": mock_container,
                        "last_heartbeat": time.time(),
                        "pod_health": {},
                        "capacity": 4
                    }
                    
            # Set up node allocations manually - all nodes are full
            app_module.node_allocations = {
                'node_1': {'allocated': 4, 'capacity': 4, 'available': 0},
                'node_2': {'allocated': 4, 'capacity': 4, 'available': 0},
                'node_3': {'allocated': 4, 'capacity': 4, 'available': 0}
            }
            
            # Update cached status to match node allocations
            with app_module.cached_status_lock:
                app_module.cached_status = {
                    'node_1': {
                        'pod_1': {'cpu_request': 4, 'cpu_usage': 3.5, 'healthy': True}
                    },
                    'node_2': {
                        'pod_2': {'cpu_request': 4, 'cpu_usage': 3.8, 'healthy': True}
                    },
                    'node_3': {
                        'pod_3': {'cpu_request': 4, 'cpu_usage': 3.5, 'healthy': True}
                    }
                }
            
            return app_module.node_allocations
            
        # Patch the add_node function to avoid calling the real one
        def mock_add_node(auto_scaled=False):
            node_id = 'node_4'
            with app_module.nodes_lock:
                app_module.nodes[node_id] = {
                    "container": mock_container,
                    "last_heartbeat": time.time(),
                    "pod_health": {},
                    "capacity": 4
                }
            
            # Also add this to the node allocations
            app_module.node_allocations[node_id] = {'allocated': 0, 'capacity': 4, 'available': 4}
            
            class MockResponse:
                def __init__(self, json_data, status_code):
                    self.json_data = json_data
                    self.status_code = status_code
                
                def get_json(self):
                    return self.json_data
            
            return MockResponse({"status": "success", "node_id": node_id}, 200)
            
        # Create a custom mock for the post request to simulate a successful pod launch
        def mock_post(*args, **kwargs):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "Success"
            return mock_response
        
        with patch.object(app_module, 'node_allocations', mock_node_allocations()):
            with patch.object(app_module, 'add_node', mock_add_node):
                with patch.object(requests, 'post', mock_post):
                    # Launch a pod with 2 CPU request - should trigger auto-scaling
                    response = self.app.post('/launch-pod', json={'pod_id': 'test_pod_1', 'cpu': 2})
                    data = json.loads(response.data)
                    
                    self.assertEqual(response.status_code, 200)
                    # The node_id should be 'node_4' since we already had 3 nodes
                    self.assertEqual(data['node_id'], 'node_4')

# Clean up patches at module level
def tearDownModule():
    docker_patcher.stop()
    requests_post_patcher.stop()
    requests_get_patcher.stop()
    file_patch.stop()

if __name__ == '__main__':
    unittest.main() 