# Fresh test file for Claude PR review
def test_claude_workflow():
    """Test function with intentional issues for Claude to review."""
    return "Testing Claude!"

# Intentional issues for Claude to identify:
def problematic_function(data):
    # Missing type hints
    # No error handling
    result = data["key"]  # Potential KeyError
    return 10 / 0  # Division by zero

class UnsafeClass:
    def __init__(self):
        self.items = []
    
    def get_item(self, index):
        # No bounds checking - potential IndexError
        return self.items[index]