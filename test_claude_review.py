# Test file for Claude PR review  
def test_function():
    """Test function to trigger Claude review."""
    return "Hello Claude!"

def another_test():
    """Another function to test workflow trigger."""
    return "Testing workflow..."

# Intentional issues for review:
def bad_function(x):
    # No type hints
    # No error handling
    return x / 0  # Division by zero

class TestClass:
    def __init__(self):
        self.data = {}
    
    def get_data(self, key):
        # No validation, could throw KeyError
        return self.data[key]
    
    def trigger_review(self):
        """Added to trigger Claude review with API key authentication."""
        return None