# Core Module

This module contains the core interfaces and domain models for the Instagram Messenger Automation system.

## Structure

```
app/core/
├── __init__.py          # Module initialization
├── interfaces.py        # All interfaces and domain models
└── README.md           # This file
```

## Interfaces

### Repository Interfaces

- **IAccountRepository**: CRUD operations for Instagram business accounts
- **IMessageRepository**: Message storage and retrieval (account-scoped)
- **IConversationRepository**: Conversation management (account-scoped)
- **IRuleRepository**: Response rule management (account-scoped)

### Messaging Interfaces

- **IMessageReceiver**: Webhook processing and message receiving (account-aware)
- **IMessageSender**: Message sending via Instagram API (account-aware)

## Domain Models

### Core Models

- **InstagramBusinessAccount**: Represents an Instagram business account with encrypted credentials
- **Message**: Represents a message (inbound or outbound)
- **Conversation**: Represents a conversation between account and user
- **ResponseRule**: Represents an automated response rule
- **InboundMessage**: Represents an incoming webhook message
- **SendMessageResponse**: Response from sending a message

### Enums

- **AccountStatus**: active, inactive, suspended
- **MessageDirection**: inbound, outbound
- **MessageType**: text, image, video, audio, sticker, story_reply, unsupported
- **MessageStatus**: pending, sent, delivered, read, failed
- **ConversationStatus**: active, archived, blocked
- **TriggerType**: keyword, pattern, intent

## Design Principles

1. **Account-Scoped**: All operations are tied to specific Instagram business accounts
2. **Interface-Driven**: Program to interfaces, not implementations
3. **Immutable Contracts**: Interfaces define clear contracts that implementations must follow
4. **Type-Safe**: All models use type hints for better IDE support and validation

## Usage Example

```python
from app.core.interfaces import (
    IMessageSender,
    IAccountRepository,
    InstagramBusinessAccount,
    SendMessageResponse
)

# Implementations will be in app/services/ and app/repositories/
class InstagramMessageSender(IMessageSender):
    async def send_message(
        self,
        account_id: str,
        recipient_id: str,
        message_text: str
    ) -> SendMessageResponse:
        # Implementation here
        pass
```

## Next Steps

1. Implement repositories in `app/repositories/`
2. Implement message sender/receiver in `app/services/`
3. Wire up dependencies in `app/core/dependencies.py`
