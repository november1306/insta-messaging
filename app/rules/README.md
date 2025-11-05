# Message Rules - KISS Principle

Simple if/elif/else rules for auto-replies. No complex configuration needed.

## For Admins: How to Add Rules

Edit `message_rules.py` and add your rules using simple Python if/elif/else:

```python
def get_reply(message_text: str, username: Optional[str] = None) -> Optional[str]:
    msg = message_text.lower()  # Case-insensitive
    
    # Rule 1
    if "order66" in msg:
        if username:
            return f"Order 66 confirmed, @{username}!"
        else:
            return "Order 66 confirmed!"
    
    # Rule 2
    elif msg.strip() == "help":
        return "Available commands: order66, help"
    
    # Rule 3
    elif "hello" in msg:
        if username:
            return f"Hello @{username}! How can we help?"
        else:
            return "Hello! How can we help?"
    
    # No match
    return None
```

## That's It!

- Add rules with `if` / `elif`
- Return the reply text
- Return `None` if no rule matches
- Use `username` parameter for personalization (optional)
- Restart server to apply changes

## Examples

### Exact Match
```python
elif msg.strip() == "help":
    return "Help text here"
```

### Contains Keyword
```python
elif "pricing" in msg:
    return "Check our pricing at example.com"
```

### Multiple Keywords (OR)
```python
elif "hello" in msg or "hi" in msg:
    return "Hello!"
```

### Multiple Keywords (AND)
```python
elif "order" in msg and "status" in msg:
    return "Check your order status at example.com/orders"
```

### Personalized Reply
```python
elif "hello" in msg:
    if username:
        return f"Hello @{username}!"
    else:
        return "Hello!"
```

## Tips

1. **Order matters**: First matching rule wins
2. **Case-insensitive**: Use `msg = message_text.lower()`
3. **Test locally**: Send test messages before deploying
4. **Keep it simple**: Don't overcomplicate
5. **Comment disabled rules**: Use `#` to disable without deleting

## Files

- `message_rules.py` - **Edit this file** to add/modify rules
- `reply_rules.py` - Interface (don't modify)
- `README.md` - This file
