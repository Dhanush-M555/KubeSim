#!/usr/bin/env python
"""
Run all real application tests sequentially. This script:
1. Runs each test one by one (which starts and stops the app)
2. Reports whether each test passed or failed
3. Exits with success only if all tests passed
"""

import os
import sys
import importlib
import time
import subprocess

# Add the parent directory to the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# List of test modules that contain real application tests
# Each module should have a main test function that returns True for success, False for failure
TEST_MODULES = [
    "tests.real_test_pod_rescheduling",
    "tests.real_test_pod_no_capacity",
]

def run_tests():
    """Run all real application tests sequentially"""
    print("=" * 80)
    print("STARTING REAL APPLICATION TESTS")
    print("=" * 80)
    
    all_passed = True
    results = {}
    
    # Make sure Docker is available
    try:
        import docker
        client = docker.from_env()
        client.ping()
    except Exception as e:
        print(f"ERROR: Docker is not available: {e}")
        print("Make sure Docker is installed and running.")
        return False
    
    # Run each test module
    for module_name in TEST_MODULES:
        module_display_name = module_name.split(".")[-1]
        print("\n" + "=" * 80)
        print(f"RUNNING TEST MODULE: {module_display_name}")
        print("=" * 80)
        
        try:
            # Dynamically import the module
            module = importlib.import_module(module_name)
            
            # Find the main test function
            test_func = None
            for name in dir(module):
                if name.startswith("test_") and callable(getattr(module, name)):
                    test_func = getattr(module, name)
                    break
            
            if test_func is None:
                print(f"ERROR: No test function found in module {module_name}")
                results[module_display_name] = False
                all_passed = False
                continue
            
            # Run the test
            start_time = time.time()
            success = test_func()
            end_time = time.time()
            
            # Record result
            results[module_display_name] = success
            if not success:
                all_passed = False
            
            # Print result
            duration = end_time - start_time
            status = "PASSED" if success else "FAILED"
            print(f"\nTest {module_display_name} {status} in {duration:.2f} seconds")
            
            # Clean up any stray processes or containers
            cleanup_docker()
            
            # Wait a bit before the next test
            time.sleep(2)
            
        except Exception as e:
            print(f"ERROR running test {module_name}: {e}")
            results[module_display_name] = False
            all_passed = False
            
            # Clean up any stray processes or containers
            cleanup_docker()
    
    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    for test_name, success in results.items():
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    overall = "✅ ALL TESTS PASSED" if all_passed else "❌ SOME TESTS FAILED"
    print(f"\nOverall result: {overall}")
    
    return all_passed

def cleanup_docker():
    """Clean up any stray Docker containers"""
    print("Cleaning up Docker environment...")
    
    # Kill any stray app.py processes
    try:
        result = subprocess.run(
            ["pkill", "-f", "python app.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    except Exception as e:
        print(f"Warning: Failed to kill stray processes: {e}")
    
    # Clean up Docker containers
    try:
        import docker
        client = docker.from_env()
        
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
        print(f"Warning: Failed to clean up Docker containers: {e}")

if __name__ == "__main__":
    # Run all tests
    success = run_tests()
    
    # Exit with appropriate status code
    sys.exit(0 if success else 1) 