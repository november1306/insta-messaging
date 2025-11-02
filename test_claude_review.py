# Test file for Claude PR review - Testing v1 workflow
def test_function():
    """Test function to trigger Claude review with v1 action."""
    return "Hello Claude! Testing v1 workflow with correct parameters!"

# Intentional issues for review:
def bad_function(x):
    # No type hints
    # No error handling
    return x / 0  # Division by zero

def another_bad_function(data):
    # Missing type hints
    # No input validation
    result = data['key']  # Could throw KeyError
    return result * 2  # Could fail if result is not numeric

class TestClass:
    def __init__(self):
        self.data = {}

    def get_data(self, key):
        # No validation, could throw KeyError
        return self.data[key]

    def unsafe_query(self, user_input):
        # SQL injection vulnerability for testing
        query = f"SELECT * FROM users WHERE id = {user_input}"
        return query