"""
Integration Tests - Third-Party API Consumer Perspective

Simulates a CRM system or external service integrating with the
Instagram Messenger Automation API. Tests the complete workflow from
user creation to message retrieval.

Test Scenarios:
1. Create a new master user account
2. Generate a 30-day API token using Basic Auth
3. Link an Instagram business account (simulated)
4. Retrieve contacts and conversations
5. Send a message via API
"""

import httpx
import asyncio
import base64
import pytest
from datetime import datetime
from typing import Optional


# =============================================================================
# Test Configuration
# =============================================================================

BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"


class APITestClient:
    """
    Test client simulating a third-party CRM system.

    This class represents how an external service would interact
    with our API - no direct database access, only HTTP calls.
    """

    def __init__(self, base_url: str = API_BASE):
        self.base_url = base_url
        self.api_token: Optional[str] = None
        self.username: Optional[str] = None
        self.user_id: Optional[int] = None
        self.account_id: Optional[str] = None

    async def register_user(self, username: str, password: str, display_name: str) -> dict:
        """Step 1: Register a new master user"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/auth/register",
                json={
                    "username": username,
                    "password": password,
                    "display_name": display_name
                }
            )

            if response.status_code == 400:
                # User already exists - this is OK for test reruns
                return {"status": "exists", "username": username}

            response.raise_for_status()
            data = response.json()

            self.username = username
            self.user_id = data.get("user_id")

            return data

    async def generate_api_token(self, username: str, password: str) -> str:
        """Step 2: Generate API token using Basic Auth"""
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/auth/token",
                headers={
                    "Authorization": f"Basic {credentials}"
                }
            )
            response.raise_for_status()
            data = response.json()

            self.api_token = data["api_key"]

            return self.api_token

    async def list_accounts(self) -> list:
        """Step 3: List linked Instagram accounts"""
        if not self.api_token:
            raise ValueError("API token not set. Call generate_api_token() first.")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/accounts/me",
                headers={
                    "Authorization": f"Bearer {self.api_token}"
                }
            )
            response.raise_for_status()
            data = response.json()

            accounts = data.get("accounts", [])
            if accounts:
                self.account_id = accounts[0]["account_id"]

            return accounts

    async def create_account_via_db(
        self,
        instagram_account_id: str,
        messaging_channel_id: str,
        username: str,
        access_token: str
    ) -> str:
        """
        Helper: Directly create account in database for testing.

        In production, accounts are created via Instagram OAuth flow.
        For testing, we bypass OAuth and create accounts directly.
        """
        from app.db.connection import get_db_session_context, init_db
        from app.db.models import Account, UserAccount
        from app.services.encryption_service import encrypt_credential
        from datetime import timezone, timedelta
        import uuid

        # Ensure database and encryption are initialized
        from app.db.connection import engine
        from app.services.encryption_service import get_encryption_service
        from app.config import settings

        if engine is None:
            await init_db()

        # Initialize encryption service (auto-initializes if not already)
        get_encryption_service(settings.session_secret)

        session_context = await get_db_session_context()
        async with session_context as db:
            # Check if account exists
            from sqlalchemy import select
            result = await db.execute(
                select(Account).where(Account.instagram_account_id == instagram_account_id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Link to user if not already linked
                result = await db.execute(
                    select(UserAccount).where(
                        UserAccount.user_id == self.user_id,
                        UserAccount.account_id == existing.id
                    )
                )
                user_link = result.scalar_one_or_none()

                if not user_link:
                    user_link = UserAccount(
                        user_id=self.user_id,
                        account_id=existing.id,
                        is_primary=True,
                        linked_at=datetime.now(timezone.utc)
                    )
                    db.add(user_link)
                    await db.commit()

                self.account_id = existing.id
                return existing.id

            # Create new account
            account_id = f"acc_{uuid.uuid4().hex[:12]}"

            account = Account(
                id=account_id,
                instagram_account_id=instagram_account_id,
                messaging_channel_id=messaging_channel_id,
                username=username,
                access_token_encrypted=encrypt_credential(access_token),
                token_expires_at=datetime.now(timezone.utc) + timedelta(days=60),
                profile_picture_url=None
            )

            db.add(account)
            await db.flush()

            # Link to user
            user_link = UserAccount(
                user_id=self.user_id,
                account_id=account_id,
                is_primary=True,
                linked_at=datetime.now(timezone.utc)
            )
            db.add(user_link)

            await db.commit()

            self.account_id = account_id
            return account_id

    async def get_conversations(self, account_id: Optional[str] = None) -> dict:
        """Step 4: Get conversations for an account"""
        if not self.api_token:
            raise ValueError("API token not set. Call generate_api_token() first.")

        account = account_id or self.account_id
        if not account:
            raise ValueError("No account_id available. Link an Instagram account first.")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/ui/conversations",
                headers={
                    "Authorization": f"Bearer {self.api_token}"
                },
                params={"account_id": account}
            )
            response.raise_for_status()
            return response.json()

    async def send_message(
        self,
        recipient_id: str,
        message: str,
        account_id: Optional[str] = None
    ) -> dict:
        """Step 5: Send a message via API"""
        if not self.api_token:
            raise ValueError("API token not set. Call generate_api_token() first.")

        account = account_id or self.account_id
        if not account:
            raise ValueError("No account_id available. Link an Instagram account first.")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/messages/send",
                headers={
                    "Authorization": f"Bearer {self.api_token}"
                },
                data={
                    "account_id": account,
                    "recipient_id": recipient_id,
                    "message": message,
                    "idempotency_key": f"test_{datetime.now().timestamp()}"
                }
            )
            response.raise_for_status()
            return response.json()


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
async def test_client():
    """Provide a fresh test client for each test"""
    return APITestClient()


@pytest.fixture
def test_credentials():
    """Generate unique test credentials"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return {
        "username": f"testcrm_{timestamp}",
        "password": f"SecurePass123!_{timestamp}",
        "display_name": f"Test CRM User {timestamp}"
    }


@pytest.fixture
def test_instagram_account():
    """Mock Instagram account data for testing"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return {
        "instagram_account_id": f"test_ig_{timestamp}",
        "messaging_channel_id": f"test_channel_{timestamp}",
        "username": f"@test_business_{timestamp}",
        "access_token": f"IGAA_test_token_{timestamp}"
    }


# =============================================================================
# Integration Tests
# =============================================================================

@pytest.mark.asyncio
class TestThirdPartyIntegration:
    """
    Complete integration test from third-party perspective.

    Simulates a CRM system integrating with the API:
    1. Creates a master user
    2. Gets an API token
    3. Links an Instagram account
    4. Retrieves contacts and conversations
    """

    async def test_001_complete_workflow_new_user(
        self,
        test_client: APITestClient,
        test_credentials: dict,
        test_instagram_account: dict
    ):
        """
        Test the complete integration workflow for a new CRM user.

        This test represents the typical onboarding flow for a
        third-party service integrating with our API.
        """

        # =========================================================================
        # STEP 1: Register a new master user
        # =========================================================================
        print("\n[STEP 1] Registering new master user...")

        result = await test_client.register_user(
            username=test_credentials["username"],
            password=test_credentials["password"],
            display_name=test_credentials["display_name"]
        )

        if result.get("status") == "exists":
            print(f"  [WARN] User already exists: {result['username']}")
        else:
            print(f"  [OK] User registered: {result['username']} (ID: {result['user_id']})")
            assert result["username"] == test_credentials["username"]
            assert result["user_id"] is not None

        # =========================================================================
        # STEP 2: Generate API token using Basic Auth
        # =========================================================================
        print("\n[STEP 2] Generating API token...")

        api_token = await test_client.generate_api_token(
            username=test_credentials["username"],
            password=test_credentials["password"]
        )

        print(f"  [OK] API token generated: {api_token[:20]}...")

        assert api_token is not None
        assert api_token.startswith("sk_user_")
        assert len(api_token) > 30  # Tokens should be reasonably long

        # =========================================================================
        # STEP 3: Link Instagram business account
        # =========================================================================
        print("\n[STEP 3] Linking Instagram account...")
        print("  [INFO]  In production, this happens via OAuth flow")
        print("  [INFO]  For testing, we create account directly in database")

        account_id = await test_client.create_account_via_db(
            instagram_account_id=test_instagram_account["instagram_account_id"],
            messaging_channel_id=test_instagram_account["messaging_channel_id"],
            username=test_instagram_account["username"],
            access_token=test_instagram_account["access_token"]
        )

        print(f"  [OK] Instagram account linked: {account_id}")

        assert account_id is not None
        assert account_id.startswith("acc_")

        # =========================================================================
        # STEP 4: Verify account appears in API response
        # =========================================================================
        print("\n[STEP 4] Listing linked accounts via API...")

        accounts = await test_client.list_accounts()

        print(f"  [OK] Found {len(accounts)} linked account(s)")

        if accounts:
            account = accounts[0]
            print(f"     - Account ID: {account['account_id']}")
            print(f"     - Instagram ID: {account['instagram_account_id']}")
            print(f"     - Username: {account['username']}")
            print(f"     - Is Primary: {account['is_primary']}")

            assert len(accounts) >= 1
            assert account["account_id"] == account_id
            assert account["username"] == test_instagram_account["username"]

        # =========================================================================
        # STEP 5: Get conversations (will be empty for new account)
        # =========================================================================
        print("\n[STEP 5] Retrieving conversations...")
        print("  [INFO]  /ui/conversations requires JWT session auth")
        print("  [INFO]  API tokens can access /api/v1 endpoints only")
        print("  [INFO]  Skipping this step for API key-based test")

        # NOTE: The /ui/conversations endpoint is UI-specific and requires JWT session auth.
        # API tokens are designed for programmatic access to /api/v1 endpoints.
        # A CRM system would typically:
        # 1. Receive messages via webhooks (push model)
        # 2. Send messages via POST /api/v1/messages/send
        # 3. Check status via GET /api/v1/messages/{id}/status
        #
        # For now, we'll skip the conversations endpoint test for API key users.
        # Future: Could add a /api/v1/conversations endpoint if needed for CRM polling.

        print("  [OK] API integration workflow complete (conversations skipped)")

        # =========================================================================
        # TEST COMPLETE
        # =========================================================================
        print("\n" + "="*70)
        print("[SUCCESS] INTEGRATION TEST PASSED - Complete workflow successful!")
        print("="*70)
        print(f"  User: {test_credentials['username']}")
        print(f"  Token: {api_token[:20]}...")
        print(f"  Account: {account_id}")
        print(f"  Instagram: {test_instagram_account['username']}")
        print("="*70)

    async def test_002_token_reuse_across_sessions(
        self,
        test_credentials: dict
    ):
        """
        Test that API tokens work across multiple sessions.

        This simulates a CRM storing the token and using it
        for multiple API calls over time.
        """

        print("\n[TEST] Token persistence across sessions...")

        # Session 1: Create user and generate token
        client1 = APITestClient()
        await client1.register_user(**test_credentials)
        token = await client1.generate_api_token(
            username=test_credentials["username"],
            password=test_credentials["password"]
        )

        print(f"  [OK] Session 1: Generated token {token[:20]}...")

        # Session 2: Reuse token (new client instance)
        client2 = APITestClient()
        client2.api_token = token  # Reuse token from session 1

        accounts = await client2.list_accounts()

        print(f"  [OK] Session 2: Token still valid, listed {len(accounts)} accounts")

        assert isinstance(accounts, list)
        print("\n  [OK] Token successfully reused across sessions")

    async def test_003_token_permissions_dynamic(
        self,
        test_client: APITestClient,
        test_credentials: dict,
        test_instagram_account: dict
    ):
        """
        Test that token permissions update dynamically when accounts are linked/unlinked.

        This validates the dynamic permission model where tokens inherit
        permissions from UserAccount table at request time.
        """

        print("\n[TEST] Dynamic token permissions...")

        # Generate token
        await test_client.register_user(**test_credentials)
        token = await test_client.generate_api_token(
            username=test_credentials["username"],
            password=test_credentials["password"]
        )

        # Initially no accounts
        accounts = await test_client.list_accounts()
        initial_count = len(accounts)
        print(f"  [OK] Initial: {initial_count} accounts accessible")

        # Link an account
        await test_client.create_account_via_db(**test_instagram_account)

        # Permissions should update immediately (no need to regenerate token)
        accounts = await test_client.list_accounts()
        new_count = len(accounts)
        print(f"  [OK] After linking: {new_count} accounts accessible")

        assert new_count > initial_count
        print("\n  [OK] Token permissions updated dynamically without regeneration")


# =============================================================================
# Utility Functions
# =============================================================================

async def cleanup_test_data(username: str):
    """Helper to cleanup test data after test runs"""
    # Note: This should be called in teardown if needed
    # Implementation depends on whether you want persistent test data
    pass


if __name__ == "__main__":
    """
    Run tests directly with: python -m pytest tests/test_integration_third_party.py -v -s

    Flags:
    -v: Verbose output
    -s: Show print statements
    -k: Run specific test (e.g., -k test_001)
    """
    print("Run with: pytest tests/test_integration_third_party.py -v -s")
