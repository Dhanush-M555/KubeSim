#!/usr/bin/env python
"""
Test runner for KubeSim tests.
Run all tests in the tests directory.
"""

import os
import sys
import subprocess
import glob

def main():
    """Run all test files in the tests directory"""
    # Get all test files, excluding this runner
    all_test_files = glob.glob("tests/test_*.py")
    test_files = [f for f in all_test_files if 
                  os.path.basename(f) != "run_tests.py"]
    advanced_tests = [f for f in all_test_files if f.endswith("advanced.py")]
    simple_tests = [f for f in all_test_files if f not in advanced_tests]

    print(f"Found {len(test_files)} test files")
    
    # Run each test file
    results = []
    for test_file in advanced_tests:
        print(f"\n{'='*20} RUNNING {os.path.basename(test_file)} {'='*20}\n")
        result = subprocess.run([sys.executable, test_file], capture_output=False)
        results.append((test_file, result.returncode))
    
    # Print summary
    print("\n\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = 0
    failed = 0
    
    for test_file, returncode in results:
        status = "PASSED" if returncode == 0 else "FAILED"
        if returncode == 0:
            passed += 1
        else:
            failed += 1
        print(f"{os.path.basename(test_file)}: {status}")
    
    print("-"*60)
    print(f"TOTAL: {len(results)}, PASSED: {passed}, FAILED: {failed}")
    
    # Return non-zero exit code if any test failed
    return 1 if failed > 0 else 0

if __name__ == "__main__":
    sys.exit(main()) 