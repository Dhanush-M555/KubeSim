#!/usr/bin/env python
"""
Run all tests for KubeSim
"""

import unittest
import sys
import os

# Add the parent directory to the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import all test modules
import tests.test_scheduling
import tests.test_node_failure
import tests.test_integration
import tests.test_edge_cases
import tests.test_pod_rescheduling

# Create a test suite containing all tests
def create_test_suite():
    """Create a test suite containing all tests"""
    test_suite = unittest.TestSuite()
    
    # Add tests from scheduling test module
    test_suite.addTest(unittest.makeSuite(tests.test_scheduling.TestSchedulingAlgorithms))
    
    # Add tests from node failure test module
    test_suite.addTest(unittest.makeSuite(tests.test_node_failure.TestNodeFailure))
    
    # Add tests from integration test module
    test_suite.addTest(unittest.makeSuite(tests.test_integration.TestIntegration))
    
    # Add tests from edge cases test module
    test_suite.addTest(unittest.makeSuite(tests.test_edge_cases.TestEdgeCases))
    
    # Add tests from pod rescheduling test module
    test_suite.addTest(unittest.makeSuite(tests.test_pod_rescheduling.TestPodRescheduling))
    
    return test_suite

if __name__ == '__main__':
    # Create test suite
    test_suite = create_test_suite()
    
    # Run the tests
    test_result = unittest.TextTestRunner().run(test_suite)
    
    # Exit with appropriate code
    sys.exit(0 if test_result.wasSuccessful() else 1) 