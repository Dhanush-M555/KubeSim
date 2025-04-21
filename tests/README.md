# KubeSim Tests

This directory contains tests for the KubeSim application.

## Test Structure

The test suite is organized into several types of tests:

1. **Basic Tests**: Simple tests that cover core functionality for each algorithm
   - `test_first_fit.py`: Tests the first-fit scheduling algorithm
   - `test_best_fit.py`: Tests the best-fit scheduling algorithm  
   - `test_worst_fit.py`: Tests the worst-fit scheduling algorithm
   - `test_pod_rescheduling.py`: Tests basic pod rescheduling capabilities
   - `test_pod_no_capacity.py`: Tests behavior when no nodes have capacity

2. **Advanced Tests**: More comprehensive tests that cover edge cases and complex scenarios
   - `test_first_fit_advanced.py`: Advanced tests for first-fit algorithm
   - `test_best_fit_advanced.py`: Advanced tests for best-fit algorithm
   - `test_worst_fit_advanced.py`: Advanced tests for worst-fit algorithm
   
3. **Integration Tests**:
   - `test_integration.py`: Tests that verify multiple components working together
   - `test_edge_cases.py`: Tests for handling unusual scenarios
   - `test_node_failure.py`: Tests for handling node failures
   - `test_scheduling.py`: General scheduling algorithm tests

## How Tests Work

All tests:

1. Modify the config.json file for the test scenario
2. Launch the actual application
3. Use the API to create nodes and pods
4. Test specific functionality (like pod rescheduling)
5. Verify the results
6. Clean up all containers and resources

Each test is self-contained and runs the application separately, ensuring a clean environment for each test.

## Running the Tests

To run all tests:

```bash
# From the project root directory
python -m tests.run_tests

# Or, with the executable
./tests/run_tests.py
```

To run a specific test file:

```bash
python tests/test_worst_fit.py
python tests/test_pod_rescheduling.py
```

## Test Requirements

The following is required to run the tests:

1. Docker to be installed and running
2. The node image to be available (run `./start.sh build` first)
3. Sufficient system resources to run multiple containers

## Test Coverage

The tests cover:

1. **Scheduling Algorithms**
   - First-fit algorithm: Picks the first node with enough capacity
   - Best-fit algorithm: Picks the node that will have the smallest remaining capacity after placing the pod
   - Worst-fit algorithm: Picks the node that will have the largest remaining capacity after placing the pod

2. **Node Failure Handling**
   - Detection of node failures based on heartbeat timeout
   - Pod rescheduling when a node fails
   - Handling of pod deletion when a node is unreachable

3. **Advanced Scenarios**
   - Complex pod rescheduling with limited capacity
   - Tie-breaking in scheduling algorithms
   - Multiple pods competing for limited resources

## Maximum Node Limit

The tests are designed to never create more than 5 nodes to accommodate resource limitations on local systems. 