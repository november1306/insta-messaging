"""
Unit tests for AccountIdentity domain class.

Tests verify:
- ID resolution (effective_channel_id property)
- Business ID detection (is_business_id method)
- Direction detection (detect_direction method)
- Customer identification (identify_other_party method)
- Message ID normalization (normalize_message_ids method)
- Factory method (from_account)

These tests are fast and have no external dependencies.
"""

import pytest
from app.domain.account_identity import AccountIdentity

pytestmark = pytest.mark.unit  # Mark all tests in this module as unit tests


# ============================================
# Test Data
# ============================================

INSTAGRAM_ACCOUNT_ID = "17841478096518771"
MESSAGING_CHANNEL_ID = "25964748486442669"
CUSTOMER_ID = "customer_12345"
ACCOUNT_ID = "acc_test123"


# ============================================
# effective_channel_id Tests
# ============================================

class TestEffectiveChannelId:
    """Tests for effective_channel_id property."""

    def test_returns_messaging_channel_id_when_set(self):
        """When messaging_channel_id is set, it takes precedence."""
        # Arrange
        identity = AccountIdentity(
            account_id=ACCOUNT_ID,
            instagram_account_id=INSTAGRAM_ACCOUNT_ID,
            messaging_channel_id=MESSAGING_CHANNEL_ID
        )

        # Act
        result = identity.effective_channel_id

        # Assert
        assert result == MESSAGING_CHANNEL_ID

    def test_falls_back_to_instagram_account_id_when_channel_is_none(self):
        """When messaging_channel_id is None, fallback to instagram_account_id."""
        # Arrange
        identity = AccountIdentity(
            account_id=ACCOUNT_ID,
            instagram_account_id=INSTAGRAM_ACCOUNT_ID,
            messaging_channel_id=None
        )

        # Act
        result = identity.effective_channel_id

        # Assert
        assert result == INSTAGRAM_ACCOUNT_ID

    def test_effective_channel_id_is_consistent(self):
        """Property should return the same value on multiple calls."""
        # Arrange
        identity = AccountIdentity(
            account_id=ACCOUNT_ID,
            instagram_account_id=INSTAGRAM_ACCOUNT_ID,
            messaging_channel_id=MESSAGING_CHANNEL_ID
        )

        # Act & Assert
        assert identity.effective_channel_id == identity.effective_channel_id


# ============================================
# business_ids Property Tests
# ============================================

class TestBusinessIds:
    """Tests for business_ids property."""

    def test_includes_instagram_account_id(self):
        """business_ids set should contain instagram_account_id."""
        # Arrange
        identity = AccountIdentity(
            account_id=ACCOUNT_ID,
            instagram_account_id=INSTAGRAM_ACCOUNT_ID,
            messaging_channel_id=MESSAGING_CHANNEL_ID
        )

        # Assert
        assert INSTAGRAM_ACCOUNT_ID in identity.business_ids

    def test_includes_messaging_channel_id_when_set(self):
        """business_ids set should contain messaging_channel_id when set."""
        # Arrange
        identity = AccountIdentity(
            account_id=ACCOUNT_ID,
            instagram_account_id=INSTAGRAM_ACCOUNT_ID,
            messaging_channel_id=MESSAGING_CHANNEL_ID
        )

        # Assert
        assert MESSAGING_CHANNEL_ID in identity.business_ids

    def test_excludes_none_messaging_channel_id(self):
        """business_ids should not contain None."""
        # Arrange
        identity = AccountIdentity(
            account_id=ACCOUNT_ID,
            instagram_account_id=INSTAGRAM_ACCOUNT_ID,
            messaging_channel_id=None
        )

        # Assert
        assert None not in identity.business_ids
        assert len(identity.business_ids) == 1


# ============================================
# is_business_id Tests
# ============================================

class TestIsBusinessId:
    """Tests for is_business_id method."""

    def test_returns_true_for_instagram_account_id(self):
        """instagram_account_id should be recognized as business ID."""
        # Arrange
        identity = AccountIdentity(
            account_id=ACCOUNT_ID,
            instagram_account_id=INSTAGRAM_ACCOUNT_ID,
            messaging_channel_id=MESSAGING_CHANNEL_ID
        )

        # Act & Assert
        assert identity.is_business_id(INSTAGRAM_ACCOUNT_ID) is True

    def test_returns_true_for_messaging_channel_id(self):
        """messaging_channel_id should be recognized as business ID."""
        # Arrange
        identity = AccountIdentity(
            account_id=ACCOUNT_ID,
            instagram_account_id=INSTAGRAM_ACCOUNT_ID,
            messaging_channel_id=MESSAGING_CHANNEL_ID
        )

        # Act & Assert
        assert identity.is_business_id(MESSAGING_CHANNEL_ID) is True

    def test_returns_false_for_customer_id(self):
        """Customer IDs should not be recognized as business ID."""
        # Arrange
        identity = AccountIdentity(
            account_id=ACCOUNT_ID,
            instagram_account_id=INSTAGRAM_ACCOUNT_ID,
            messaging_channel_id=MESSAGING_CHANNEL_ID
        )

        # Act & Assert
        assert identity.is_business_id(CUSTOMER_ID) is False

    def test_returns_true_for_instagram_id_when_channel_is_none(self):
        """Should recognize instagram_account_id even when channel is None."""
        # Arrange
        identity = AccountIdentity(
            account_id=ACCOUNT_ID,
            instagram_account_id=INSTAGRAM_ACCOUNT_ID,
            messaging_channel_id=None
        )

        # Act & Assert
        assert identity.is_business_id(INSTAGRAM_ACCOUNT_ID) is True


# ============================================
# detect_direction Tests
# ============================================

class TestDetectDirection:
    """Tests for detect_direction method."""

    def test_returns_outbound_when_sender_is_business(self):
        """Messages from business account are outbound."""
        # Arrange
        identity = AccountIdentity(
            account_id=ACCOUNT_ID,
            instagram_account_id=INSTAGRAM_ACCOUNT_ID,
            messaging_channel_id=MESSAGING_CHANNEL_ID
        )

        # Act
        result = identity.detect_direction(MESSAGING_CHANNEL_ID)

        # Assert
        assert result == "outbound"

    def test_returns_inbound_when_sender_is_customer(self):
        """Messages from customers are inbound."""
        # Arrange
        identity = AccountIdentity(
            account_id=ACCOUNT_ID,
            instagram_account_id=INSTAGRAM_ACCOUNT_ID,
            messaging_channel_id=MESSAGING_CHANNEL_ID
        )

        # Act
        result = identity.detect_direction(CUSTOMER_ID)

        # Assert
        assert result == "inbound"

    def test_returns_outbound_for_instagram_account_id_sender(self):
        """Messages from instagram_account_id are also outbound."""
        # Arrange
        identity = AccountIdentity(
            account_id=ACCOUNT_ID,
            instagram_account_id=INSTAGRAM_ACCOUNT_ID,
            messaging_channel_id=MESSAGING_CHANNEL_ID
        )

        # Act
        result = identity.detect_direction(INSTAGRAM_ACCOUNT_ID)

        # Assert
        assert result == "outbound"


# ============================================
# identify_other_party Tests
# ============================================

class TestIdentifyOtherParty:
    """Tests for identify_other_party method."""

    def test_returns_recipient_when_sender_is_business(self):
        """For outbound messages, the other party is the recipient."""
        # Arrange
        identity = AccountIdentity(
            account_id=ACCOUNT_ID,
            instagram_account_id=INSTAGRAM_ACCOUNT_ID,
            messaging_channel_id=MESSAGING_CHANNEL_ID
        )

        # Act
        result = identity.identify_other_party(
            sender_id=MESSAGING_CHANNEL_ID,
            recipient_id=CUSTOMER_ID
        )

        # Assert
        assert result == CUSTOMER_ID

    def test_returns_sender_when_recipient_is_business(self):
        """For inbound messages, the other party is the sender."""
        # Arrange
        identity = AccountIdentity(
            account_id=ACCOUNT_ID,
            instagram_account_id=INSTAGRAM_ACCOUNT_ID,
            messaging_channel_id=MESSAGING_CHANNEL_ID
        )

        # Act
        result = identity.identify_other_party(
            sender_id=CUSTOMER_ID,
            recipient_id=MESSAGING_CHANNEL_ID
        )

        # Assert
        assert result == CUSTOMER_ID


# ============================================
# normalize_message_ids Tests
# ============================================

class TestNormalizeMessageIds:
    """Tests for normalize_message_ids method."""

    def test_outbound_uses_effective_channel_id_as_sender(self):
        """Outbound messages should have effective_channel_id as sender."""
        # Arrange
        identity = AccountIdentity(
            account_id=ACCOUNT_ID,
            instagram_account_id=INSTAGRAM_ACCOUNT_ID,
            messaging_channel_id=MESSAGING_CHANNEL_ID
        )

        # Act
        sender, recipient = identity.normalize_message_ids(
            sender_id=INSTAGRAM_ACCOUNT_ID,  # Business sent
            customer_id=CUSTOMER_ID
        )

        # Assert
        assert sender == MESSAGING_CHANNEL_ID  # Normalized to effective
        assert recipient == CUSTOMER_ID

    def test_inbound_preserves_customer_as_sender(self):
        """Inbound messages should preserve customer as sender."""
        # Arrange
        identity = AccountIdentity(
            account_id=ACCOUNT_ID,
            instagram_account_id=INSTAGRAM_ACCOUNT_ID,
            messaging_channel_id=MESSAGING_CHANNEL_ID
        )

        # Act
        sender, recipient = identity.normalize_message_ids(
            sender_id=CUSTOMER_ID,  # Customer sent
            customer_id=CUSTOMER_ID
        )

        # Assert
        assert sender == CUSTOMER_ID
        assert recipient == MESSAGING_CHANNEL_ID  # Normalized to effective


# ============================================
# from_account Factory Tests
# ============================================

class TestFromAccount:
    """Tests for from_account class method."""

    def test_creates_identity_from_account_model(self, sample_account):
        """Factory should create AccountIdentity with all fields populated."""
        # Act
        identity = AccountIdentity.from_account(sample_account)

        # Assert
        assert identity.account_id == sample_account.id
        assert identity.instagram_account_id == sample_account.instagram_account_id
        assert identity.messaging_channel_id == sample_account.messaging_channel_id

    def test_creates_identity_with_none_messaging_channel(self, sample_account_no_channel):
        """Factory should handle None messaging_channel_id."""
        # Act
        identity = AccountIdentity.from_account(sample_account_no_channel)

        # Assert
        assert identity.account_id == sample_account_no_channel.id
        assert identity.messaging_channel_id is None
        assert identity.effective_channel_id == sample_account_no_channel.instagram_account_id


# ============================================
# Immutability Tests
# ============================================

class TestImmutability:
    """Tests verifying AccountIdentity is immutable (frozen dataclass)."""

    def test_cannot_modify_account_id(self):
        """account_id should not be modifiable."""
        # Arrange
        identity = AccountIdentity(
            account_id=ACCOUNT_ID,
            instagram_account_id=INSTAGRAM_ACCOUNT_ID,
            messaging_channel_id=MESSAGING_CHANNEL_ID
        )

        # Act & Assert
        with pytest.raises(AttributeError):
            identity.account_id = "new_value"

    def test_cannot_modify_instagram_account_id(self):
        """instagram_account_id should not be modifiable."""
        # Arrange
        identity = AccountIdentity(
            account_id=ACCOUNT_ID,
            instagram_account_id=INSTAGRAM_ACCOUNT_ID,
            messaging_channel_id=MESSAGING_CHANNEL_ID
        )

        # Act & Assert
        with pytest.raises(AttributeError):
            identity.instagram_account_id = "new_value"
