# KubeSim Tests

This directory contains tests for the KubeSim application.

## Test Types

There are two types of tests:

1. **Mocked Tests**: Use unittest and mocks to simulate the application behavior.
2. **Real Application Tests**: Launch the actual application and test its behavior.

## Running Mocked Tests

To run the mocked tests:

```bash
python -m tests.run_tests
```

These tests use unittest and mocks to test the application logic without actually running the application or Docker containers.

## Running Real Application Tests

To run the real application tests:

```bash
python -m tests.run_real_tests
```

These tests actually launch the application and Docker containers to test the real system behavior. They clean up after themselves, but require:

1. Docker to be installed and running
2. The node image to be available (run `./start.sh build` first)
3. Sufficient system resources to run multiple containers

### Real Tests Include:

- **Pod Rescheduling**: Tests that pods get properly rescheduled when a node is deleted
- **Pod No Capacity**: Tests that the system correctly reports when pods cannot be rescheduled due to lack of capacity

## How Real Tests Work

The real tests:

1. Modify the config.json file for the test scenario
2. Launch the actual application
3. Use the API to create nodes and pods
4. Test specific functionality (like pod rescheduling)
5. Verify the results
6. Clean up all containers and resources

Each test is self-contained and runs the application separately, ensuring a clean environment for each test.

## Test Structure

- `test_scheduling.py`: Tests the scheduling algorithms (first-fit, best-fit, worst-fit)
- `test_node_failure.py`: Tests the handling of node failures and pod rescheduling
- `test_integration.py`: Integration tests that verify all components working together
- `run_tests.py`: Test runner script to execute all tests

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
python -m unittest tests.test_scheduling
python -m unittest tests.test_node_failure
python -m unittest tests.test_integration
```

## Test Requirements

The tests use Python's `unittest` framework and mock the necessary components to avoid requiring an actual Docker environment. The following packages are required:

- unittest (built-in)
- mock (part of unittest from Python 3.3+)

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

3. **Integration**
   - Complete workflows for all scheduling algorithms
   - Node failure recovery and auto-scaling

## Maximum Node Limit

As requested, the tests are designed to never create more than 5 nodes to accommodate resource limitations on local systems. 