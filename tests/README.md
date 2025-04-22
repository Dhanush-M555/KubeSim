# KubeSim Tests

This folder contains a suite of tests for KubeSim, designed to verify the functionality of the scheduling algorithms and failure recovery mechanisms.

## Test Structure

The tests are organized into two main categories:

1. **Basic Algorithm Tests**: Simple tests for each scheduling algorithm
   - `test_first_fit.py` - Tests for the First-Fit scheduling algorithm
   - `test_best_fit.py` - Tests for the Best-Fit scheduling algorithm  
   - `test_worst_fit.py` - Tests for the Worst-Fit scheduling algorithm

2. **Advanced Tests**: Complex scenarios and edge cases
   - `test_first_fit_advanced.py` - Complex tests for First-Fit algorithm
   - `test_best_fit_advanced.py` - Complex tests for Best-Fit algorithm
   - `test_worst_fit_advanced.py` - Complex tests for Worst-Fit algorithm
   - `test_pod_rescheduling.py` - Tests pod rescheduling across all algorithms
   - `test_node_failure.py` - Tests node failure recovery
   - `test_pod_no_capacity.py` - Tests behavior when there's insufficient capacity

## How Tests Work

The tests use Python's test framework to verify that KubeSim's scheduling and rescheduling logic works as expected. Each test:

1. Configures KubeSim with specific settings
2. Creates nodes with defined capacities
3. Places pods on nodes according to test scenarios
4. Verifies pod placement according to the scheduling algorithm
5. Tests edge cases like node deletion, pod rescheduling, and capacity constraints

## Running Tests

To run all tests:
```
python tests/run_tests.py
```

To run a specific test file:
```
python tests/test_file_name.py
```

## Requirements

The tests require:
- Docker installed and running
- Python 3.6 or higher
- Access to port 5000 (for the KubeSim API)

## Test Coverage

The test suite covers:
- All three scheduling algorithms (First-Fit, Best-Fit, Worst-Fit)
- Pod placement according to algorithm rules
- Node failure and pod rescheduling
- Auto-scaling behavior
- Edge cases like insufficient capacity or ties between nodes

Tests are designed to never create more than 5 nodes to accommodate resource limitations on test systems. 