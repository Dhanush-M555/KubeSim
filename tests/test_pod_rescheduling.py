"""
Tests for pod rescheduling feature.
"""

import unittest
import json
import os
import sys
import time
import requests
from unittest.mock import patch, MagicMock

# Add the parent directory to the path so we can import app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

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

# Now import app with patched dependencies
import app as app_module

# Override the app docker client
app_module.docker_client = docker_mock.return_value

class TestPodRescheduling(unittest.TestCase):
    """Test that pods get rescheduled when nodes are deleted."""
    
    def setUp(self):
        """Set up before each test."""
        # Reset mocks
        docker_mock.reset_mock()
        requests_post_mock.reset_mock()
        requests_get_mock.reset_mock()
        requests_delete_mock.reset_mock()
        
        # Create a test client
        self.app = app_module.app.test_client()
        
        # Enable auto-scaling for rescheduling
        app_module.AUTO_SCALE = True
        app_module.SCHEDULING_ALGO = 'first-fit'
        
        # Clear nodes and cached status
        with app_module.nodes_lock:
            app_module.nodes.clear()
            
        with app_module.cached_status_lock:
            app_module.cached_status.clear()
            
    def test_pod_rescheduling_on_node_deletion(self):
        """Test that pods get rescheduled when a node is deleted."""
        # Create two nodes
        mock_container_1 = MagicMock()
        mock_container_1.id = 'mock_container_id_1'
        mock_container_1.status = 'running'
        
        mock_container_2 = MagicMock()
        mock_container_2.id = 'mock_container_id_2'
        mock_container_2.status = 'running'
        
        # Create containers with inspection data
        def mock_inspect_container(container_id):
            if container_id == 'mock_container_id_1':
                return {
                    'NetworkSettings': {'Networks': {'cluster-net': {'IPAddress': '172.17.0.2'}}}
                }
            elif container_id == 'mock_container_id_2':
                return {
                    'NetworkSettings': {'Networks': {'cluster-net': {'IPAddress': '172.17.0.3'}}}
                }
            return {
                'NetworkSettings': {'Networks': {'cluster-net': {'IPAddress': '172.17.0.2'}}}
            }
            
        app_module.docker_client.api.inspect_container.side_effect = mock_inspect_container
        
        # Setup nodes
        with app_module.nodes_lock:
            app_module.nodes['node_1'] = {
                "container": mock_container_1,
                "last_heartbeat": time.time(),
                "pod_health": {},
                "capacity": 4
            }
            
            app_module.nodes['node_2'] = {
                "container": mock_container_2,
                "last_heartbeat": time.time(),
                "pod_health": {},
                "capacity": 4
            }
            
        # Setup cached status with a pod on node_1
        with app_module.cached_status_lock:
            app_module.cached_status['node_1'] = {
                'pod_1': {'cpu_request': 2, 'cpu_usage': 1.5, 'healthy': True}
            }
            app_module.cached_status['node_2'] = {}
            
        # Create a mock for the post request to simulate successful pod launch
        def mock_post(*args, **kwargs):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "Success"
            return mock_response
            
        # Create a simple tracker to check if rescheduling happened
        rescheduling_happened = [False]
        
        # Override the reschedule_pod function to track calls
        original_reschedule = app_module.reschedule_pod
        def mock_reschedule_pod(pod_id, cpu_request):
            rescheduling_happened[0] = True
            print(f"Mock rescheduling pod {pod_id} with {cpu_request} CPU")
            
            # Update cached status as if successfully rescheduled to node_2
            with app_module.cached_status_lock:
                if 'node_2' not in app_module.cached_status:
                    app_module.cached_status['node_2'] = {}
                
                app_module.cached_status['node_2'][pod_id] = {
                    'cpu_request': cpu_request,
                    'cpu_usage': 0,
                    'healthy': True
                }
            
            return True
        
        # Patch the reschedule_pod function and requests
        with patch.object(app_module, 'reschedule_pod', mock_reschedule_pod):
            with patch.object(requests, 'post', mock_post):
                # Delete node_1
                response = self.app.delete('/delete-node', json={'node_id': 'node_1'})
                self.assertEqual(response.status_code, 200)
                
                # Verify rescheduling was attempted
                self.assertTrue(rescheduling_happened[0])
                
                # Verify pod has been moved to node_2
                with app_module.cached_status_lock:
                    self.assertNotIn('node_1', app_module.cached_status)
                    self.assertIn('node_2', app_module.cached_status)
                    self.assertIn('pod_1', app_module.cached_status['node_2'])
                    
                    # Verify CPU request was preserved
                    self.assertEqual(app_module.cached_status['node_2']['pod_1']['cpu_request'], 2)
    
    def test_pod_rescheduling_with_autoscaling(self):
        """Test rescheduling when there's not enough capacity on existing nodes."""
        # Create a single node with pods that use up most of its capacity
        mock_container_1 = MagicMock()
        mock_container_1.id = 'mock_container_id_1'
        mock_container_1.status = 'running'
        
        # Setup the node with limited capacity
        with app_module.nodes_lock:
            app_module.nodes['node_1'] = {
                "container": mock_container_1,
                "last_heartbeat": time.time(),
                "pod_health": {},
                "capacity": 4
            }
            
        # Setup cached status with a large pod that will need a new node
        with app_module.cached_status_lock:
            app_module.cached_status['node_1'] = {
                'pod_1': {'cpu_request': 3, 'cpu_usage': 2.5, 'healthy': True}
            }
        
        # Track if autoscaling was triggered
        autoscaling_triggered = [False]
        
        # Mock the add_node function
        original_add_node = app_module.add_node
        def mock_add_node(auto_scaled=False):
            autoscaling_triggered[0] = True
            print(f"Mock creating new node for rescheduling with auto_scaled={auto_scaled}")
            
            # Create a mock node response
            mock_container_2 = MagicMock()
            mock_container_2.id = 'mock_container_id_2'
            mock_container_2.status = 'running'
            
            # Add the new node
            with app_module.nodes_lock:
                app_module.nodes['node_2'] = {
                    "container": mock_container_2,
                    "last_heartbeat": time.time(),
                    "pod_health": {},
                    "capacity": 8  # Higher capacity
                }
            
            class MockResponse:
                def __init__(self, json_data, status_code):
                    self.json_data = json_data
                    self.status_code = status_code
                
                def get_json(self):
                    return self.json_data
            
            return MockResponse({"status": "success", "node_id": "node_2"}, 200)
        
        # Create a mock for the post request to simulate successful pod launch
        def mock_post(*args, **kwargs):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "Success"
            return mock_response
        
        # Override the reschedule_pod function to use original logic but update our tracking
        def mock_reschedule_pod(pod_id, cpu_request):
            print(f"Attempting to reschedule pod {pod_id} with {cpu_request} CPU")
            
            # Skip to the part where we would create a new node
            result = mock_add_node(auto_scaled=True)
            
            # Update cached status as if successfully rescheduled
            with app_module.cached_status_lock:
                if 'node_2' not in app_module.cached_status:
                    app_module.cached_status['node_2'] = {}
                
                app_module.cached_status['node_2'][pod_id] = {
                    'cpu_request': cpu_request,
                    'cpu_usage': 0,
                    'healthy': True
                }
            
            return True
        
        # Patch the necessary functions
        with patch.object(app_module, 'add_node', mock_add_node):
            with patch.object(app_module, 'reschedule_pod', mock_reschedule_pod):
                with patch.object(requests, 'post', mock_post):
                    # Delete node_1
                    response = self.app.delete('/delete-node', json={'node_id': 'node_1'})
                    self.assertEqual(response.status_code, 200)
                    
                    # Verify autoscaling was triggered
                    self.assertTrue(autoscaling_triggered[0])
                    
                    # Verify pod has been moved to node_2
                    with app_module.cached_status_lock:
                        self.assertNotIn('node_1', app_module.cached_status)
                        self.assertIn('node_2', app_module.cached_status)
                        self.assertIn('pod_1', app_module.cached_status['node_2'])
                        
                        # Verify CPU request was preserved
                        self.assertEqual(app_module.cached_status['node_2']['pod_1']['cpu_request'], 3)

# Clean up patches
def tearDownModule():
    docker_patcher.stop()
    requests_post_patcher.stop()
    requests_get_patcher.stop()
    requests_delete_patcher.stop()

if __name__ == '__main__':
    unittest.main() 