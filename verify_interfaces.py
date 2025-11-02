"""
Verification script for core interfaces and domain models.
This script verifies that all required interfaces and models are properly defined.
"""

from app.core import (
    # Enums
    AccountStatus,
    MessageDirection,
    MessageType,
    MessageStatus,
    ConversationStatus,
    TriggerType,
    
    # Domain Models
    InstagramBusinessAccount,
    Message,
    Conversation,
    ResponseRule,
    InboundMessage,
    SendMessageResponse,
    
    # Repository Interfaces
    IAccountRepository,
    IMessageRepository,
    IConversationRepository,
    IRuleRepository,
    
    # Messaging Interfaces
    IMessageReceiver,
    IMessageSender,
)


def verify_enums():
    """Verify all enums are properly defined."""
    print("✓ Verifying Enums...")
    assert AccountStatus.ACTIVE == "active"
    assert MessageDirection.INBOUND == "inbound"
    assert MessageType.TEXT == "text"
    assert MessageStatus.DELIVERED == "delivered"
    assert ConversationStatus.ACTIVE == "active"
    assert TriggerType.KEYWORD == "keyword"
    print("  ✓ All enums verified")


def verify_domain_models():
    """Verify all domain models can be instantiated."""
    print("✓ Verifying Domain Models...")
    
    # InstagramBusinessAccount
    account = InstagramBusinessAccount(
        id="123",
        username="test_account",
        display_name="Test Account",
        access_token_encrypted="encrypted_token",
        app_secret_encrypted="encrypted_secret",
        webhook_verify_token="verify_token"
    )
    assert account.id == "123"
    
    # Message
    message = Message(
        id="msg_123",
        account_id="123",
        conversation_id="conv_123",
        direction=MessageDirection.INBOUND,
        sender_id="sender_123",
        recipient_id="recipient_123",
        message_text="Hello"
    )
    assert message.message_text == "Hello"
    
    # Conversation
    conversation = Conversation(
        id="conv_123",
        account_id="123",
        participant_id="user_123"
    )
    assert conversation.id == "conv_123"
    
    # ResponseRule
    rule = ResponseRule(
        id=1,
        account_id="123",
        name="Test Rule",
        trigger_type=TriggerType.KEYWORD,
        trigger_value="hello",
        response_template="Hi there!"
    )
    assert rule.name == "Test Rule"
    
    # InboundMessage
    inbound = InboundMessage(
        message_id="msg_123",
        sender_id="sender_123",
        recipient_id="recipient_123",
        text="Hello"
    )
    assert inbound.text == "Hello"
    
    # SendMessageResponse
    response = SendMessageResponse(
        success=True,
        message_id="msg_123",
        recipient_id="recipient_123"
    )
    assert response.success is True
    
    print("  ✓ All domain models verified")


def verify_interfaces():
    """Verify all interfaces are properly defined."""
    print("✓ Verifying Interfaces...")
    
    # Repository Interfaces
    assert hasattr(IAccountRepository, 'get_by_id')
    assert hasattr(IAccountRepository, 'get_by_username')
    assert hasattr(IAccountRepository, 'create')
    assert hasattr(IAccountRepository, 'update')
    assert hasattr(IAccountRepository, 'get_active_accounts')
    
    assert hasattr(IMessageRepository, 'create')
    assert hasattr(IMessageRepository, 'get_conversation_history')
    
    assert hasattr(IConversationRepository, 'get_or_create')
    assert hasattr(IConversationRepository, 'update_last_message_time')
    
    assert hasattr(IRuleRepository, 'get_active_rules')
    assert hasattr(IRuleRepository, 'find_matching_rule')
    
    # Messaging Interfaces
    assert hasattr(IMessageReceiver, 'receive_webhook')
    assert hasattr(IMessageReceiver, 'validate_signature')
    assert hasattr(IMessageReceiver, 'process_message')
    
    assert hasattr(IMessageSender, 'send_message')
    assert hasattr(IMessageSender, 'send_template')
    
    print("  ✓ All interfaces verified")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("VERIFYING CORE INTERFACES AND DOMAIN MODELS")
    print("="*60 + "\n")
    
    try:
        verify_enums()
        verify_domain_models()
        verify_interfaces()
        
        print("\n" + "="*60)
        print("✓ ALL VERIFICATIONS PASSED!")
        print("="*60 + "\n")
        
        print("Summary:")
        print("  • 6 Enums defined")
        print("  • 6 Domain Models defined")
        print("  • 6 Interfaces defined (4 Repository + 2 Messaging)")
        print("  • All components are properly importable")
        print("\nTask 3 is complete! ✓")
        
    except Exception as e:
        print(f"\n✗ VERIFICATION FAILED: {e}")
        raise
