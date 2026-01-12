# Integration Tests

Comprehensive test suite for the Instagram Messenger Automation Platform.

## Overview

This test suite validates the complete API workflow from a **third-party consumer perspective** (e.g., CRM systems, external integrations).

### Test Philosophy

- **Black Box Testing**: Tests interact only through HTTP APIs, not direct database access (except for test data setup)
- **Real-World Scenarios**: Simulates actual CRM integration workflows
- **End-to-End Coverage**: From user registration to message retrieval

## Test Structure

```
tests/
├── __init__.py                          # Package initialization
├── test_integration_third_party.py      # Main integration tests
├── README.md                            # This file
└── (future test files...)
```

## Running Tests

### Prerequisites

1. **Backend must be running**:
   ```bash
   # Start backend server
   scripts\win\dev-backend.bat

   # Or manually:
   venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Install test dependencies** (if not already installed):
   ```bash
   venv\Scripts\pip.exe install pytest pytest-asyncio httpx
   ```

### Run All Tests

```bash
# Activate virtual environment
venv\Scripts\activate.bat

# Run all tests with verbose output
pytest tests/ -v -s

# Or from project root
python -m pytest tests/ -v -s
```

### Run Specific Tests

```bash
# Run only integration tests
pytest tests/test_integration_third_party.py -v -s

# Run a specific test function
pytest tests/test_integration_third_party.py::TestThirdPartyIntegration::test_001_complete_workflow_new_user -v -s

# Run tests matching a pattern
pytest tests/ -k "workflow" -v -s
```

### Test Flags

- `-v` or `--verbose`: Show detailed test names
- `-s`: Show print statements (important for seeing test progress)
- `-x`: Stop on first failure
- `--tb=short`: Short traceback format
- `-k EXPRESSION`: Run tests matching expression
- `-m MARKER`: Run tests with specific marker

## Test Scenarios

### test_integration_third_party.py

**Purpose**: Validates complete API integration from third-party perspective

#### Test 001: Complete Workflow (New User)
Simulates a CRM system integrating with the API:

1. ✅ **User Registration**: Create a new master user account
2. ✅ **Token Generation**: Get 30-day API token via Basic Auth
3. ✅ **Account Linking**: Connect Instagram business account
4. ✅ **Account Listing**: Verify account appears in API response
5. ✅ **Conversations**: Retrieve conversation list (empty for new account)

**Expected Output**:
```
[STEP 1] Registering new master user...
  ✅ User registered: testcrm_20260108_233000 (ID: 5)

[STEP 2] Generating API token...
  ✅ API token generated: sk_user_ABC123...

[STEP 3] Linking Instagram account...
  ✅ Instagram account linked: acc_xyz789

[STEP 4] Listing linked accounts via API...
  ✅ Found 1 linked account(s)
     - Account ID: acc_xyz789
     - Instagram ID: test_ig_20260108233000
     - Username: @test_business_20260108233000
     - Is Primary: True

[STEP 5] Retrieving conversations...
  ✅ Conversations retrieved: 0 conversations

======================================================================
✅ INTEGRATION TEST PASSED - Complete workflow successful!
======================================================================
```

#### Test 002: Token Persistence
Validates that API tokens work across multiple client sessions.

**Purpose**: Ensure CRM systems can store tokens and reuse them.

#### Test 003: Dynamic Permissions
Validates that token permissions update automatically when accounts are linked/unlinked.

**Purpose**: Test the dynamic permission model (no need to regenerate tokens).

## Test Data

### Auto-Generated Test Data

Tests automatically generate unique test data using timestamps:

- **Usernames**: `testcrm_YYYYMMDD_HHMMSS`
- **Instagram IDs**: `test_ig_YYYYMMDDHHMMSS`
- **Accounts**: `acc_xyz789...`

### Test Data Cleanup

Test data persists in the database for debugging. To clean up:

```bash
# Manual cleanup (from Python)
python
>>> from app.db.connection import get_async_session
>>> from app.db.models import User
>>> # Delete test users manually if needed
```

Or reset the database entirely:
```bash
python reset_db_and_migrations.py
```

## Debugging Tests

### View Detailed Output

```bash
# Show all print statements and logs
pytest tests/test_integration_third_party.py -v -s --log-cli-level=DEBUG
```

### Debug Single Test

```bash
# Run one test with Python debugger
pytest tests/test_integration_third_party.py::TestThirdPartyIntegration::test_001_complete_workflow_new_user -v -s --pdb
```

### Check Backend Logs

While tests run, check backend server output:
```bash
# Backend logs show all API requests
tail -f C:\Users\tol13\AppData\Local\Temp\claude\C--workspace-insta-auto\tasks\<task-id>.output
```

## Common Issues

### 1. "Connection refused" or "Connection error"

**Problem**: Backend server not running

**Solution**:
```bash
# Start backend first
scripts\win\dev-backend.bat
```

### 2. "ModuleNotFoundError: No module named 'app'"

**Problem**: Running tests outside virtual environment or wrong directory

**Solution**:
```bash
# Activate venv and run from project root
venv\Scripts\activate.bat
cd C:\workspace\insta-auto
pytest tests/ -v -s
```

### 3. "User already exists" errors

**Problem**: Test user from previous run still exists

**Solution**: This is expected behavior. Tests handle existing users gracefully. To start fresh:
```bash
python reset_db_and_migrations.py
```

### 4. Tests pass but no output shown

**Problem**: Missing `-s` flag

**Solution**:
```bash
# Add -s to show print statements
pytest tests/ -v -s
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: Start backend
        run: |
          uvicorn app.main:app --host 0.0.0.0 --port 8000 &
          sleep 5
      - name: Run tests
        run: pytest tests/ -v -s
```

## Contributing

When adding new tests:

1. **Follow the naming convention**: `test_XXX_descriptive_name`
2. **Add docstrings**: Explain what the test validates
3. **Use fixtures**: Reuse test data setup via pytest fixtures
4. **Print progress**: Use print statements for visual feedback during test runs
5. **Handle cleanup**: Ensure tests don't interfere with each other

## Future Test Plans

- `test_auth.py`: Authentication edge cases (expired tokens, invalid credentials)
- `test_webhooks.py`: Instagram webhook signature validation
- `test_messages.py`: Message sending, idempotency, status checks
- `test_permissions.py`: Access control and authorization
- `test_performance.py`: Load testing and rate limiting

---

**Questions?** Check the main project README or the API documentation at http://localhost:8000/docs
