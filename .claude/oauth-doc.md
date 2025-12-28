 ✶ Insight ─────────────────────────────────────
  Plan Architecture Highlights:
  1. Security-First: Fernet encryption replaces base64 (real crypto, not encoding)
  2. YAGNI-Compliant: Reuses SESSION_SECRET for encryption key (no new config)
  3. Backward Compatible: InstagramClient accepts both old (settings) and new (access_token) patterns
  4. Zero Webhook Changes: Current recipient_id routing already supports multi-account
  ─────────────────────────────────────────────────

  Plan Summary

  Scope: Transform single-account system into OAuth-based multi-user architecture

  Key Features:
  - ✅ Shared Instagram app (users authorize with your single Facebook app)
  - ✅ One user → multiple Instagram accounts (many-to-many relationship)
  - ✅ Dual auth (username/password + Instagram OAuth)
  - ✅ Proper encryption (Fernet replaces base64)
  - ✅ Account switcher UI
  - ✅ Migration for existing account

  Implementation Timeline: 10 days
  - Week 1: Backend (encryption, OAuth flow, database, API endpoints)
  - Week 2: Frontend (UI components, stores) + testing + deployment

  Critical Changes:
  - 9 new files (services, components, migration)
  - 10 modified files (models, config, clients, views)
  - 3 new database tables (UserAccount, OAuthState, + enhancements)

  No Breaking Changes:
  - Instagram client backward compatible
  - Webhooks continue working as-is
  - Existing username/password login preserved

  The plan is ready for implementation! 🚀

───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
 Ready to code?

 Here is Claude's plan:
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
 Instagram OAuth Multi-Account Implementation Plan

 Overview

 Transform the current single-account system into a multi-user OAuth-based architecture where users authenticate with their own Instagram Business Accounts and manage their own
 messages.

 User Requirements (Confirmed)

 - ✅ Shared Instagram App - Single Facebook/Instagram app for all users
 - ✅ Multi-Account per User - Users can link and manage multiple Instagram accounts
 - ✅ Dual Authentication - Keep username/password + add Instagram OAuth
 - ✅ Permission: instagram_manage_messages (DM automation)

 Current Architecture

 - Single Instagram account via settings.instagram_business_account_id
 - InstagramClient uses global settings.instagram_page_access_token
 - JWT auth for users (username/password only)
 - Account model exists but tokens stored as base64 (not secure)
 - Webhooks already route by recipient_id (no changes needed)

 Implementation Strategy

 Phase 1: Security & Database Foundation

 1.1 Create Fernet Encryption Service

 File: app/services/encryption_service.py (NEW)
 - Replace base64 encoding with proper Fernet encryption
 - Derive key from existing SESSION_SECRET (no new config needed)
 - Methods: encrypt(plaintext), decrypt(encrypted)

 1.2 Database Schema Changes

 File: app/db/models.py

 New Tables:
 1. UserAccount (Many-to-many relationship)
   - id (Integer, PK)
   - user_id (FK to users)
   - account_id (FK to accounts)
   - role (String: 'owner', 'admin', 'viewer')
   - is_primary (Boolean - default account for user)
   - linked_at (DateTime)
   - Unique index on (user_id, account_id)
 2. OAuthState (CSRF protection)
   - state (String(64), PK - random token)
   - user_id (FK to users, nullable)
   - redirect_uri (String(500))
   - created_at, expires_at (10-minute expiration)
   - Index on expires_at for cleanup

 Enhanced User Model:
 - oauth_provider (String, nullable - 'instagram')
 - oauth_provider_id (String, nullable - Instagram user ID)
 - oauth_email (String, nullable)
 - Index on (oauth_provider, oauth_provider_id)

 Enhanced Account Model:
 - token_expires_at (DateTime, nullable)
 - refresh_token_encrypted (Text, nullable)
 - scopes (Text, nullable - JSON array)
 - profile_picture_url (String(500), nullable)
 - biography (Text, nullable)
 - followers_count (Integer, nullable)
 - last_synced_at (DateTime, nullable)
 - Make crm_webhook_url and webhook_secret nullable
 - Index on token_expires_at

 1.3 Alembic Migration

 File: alembic/versions/xxx_add_oauth_support.py (NEW)
 - Create new tables (user_accounts, oauth_states)
 - Add columns to users and accounts tables
 - Make CRM fields nullable on accounts table

 Phase 2: OAuth Flow Backend

 2.1 OAuth Service

 File: app/services/oauth_service.py (NEW)

 Methods:
 - create_authorization_url(db, user_id, redirect_after_oauth) → (state, auth_url)
   - Generate CSRF state token
   - Store in oauth_states table
   - Build Instagram OAuth URL with scope instagram_manage_messages
 - validate_state(db, state) → OAuthState | None
   - Check state exists and not expired
 - exchange_code_for_token(db, code, user_id) → (Account, is_new)
   - Exchange authorization code for short-lived token
   - Upgrade to long-lived token (60 days)
   - Fetch Instagram profile (username, profile_picture_url, biography)
   - Create/update Account with Fernet-encrypted token
   - Link to user via UserAccount table
 - delete_state(db, state)
   - Clean up after successful callback
 - cleanup_expired_states(db)
   - Background task for expired state cleanup

 2.2 OAuth API Endpoints

 File: app/api/oauth.py (NEW)

 Routes:
 - GET /oauth/instagram/authorize
   - Requires JWT session (user must be logged in)
   - Generates state token and redirects to Instagram
 - GET /oauth/instagram/callback
   - Receives code and state from Instagram
   - Validates state, exchanges code for token
   - Creates/links account
   - Redirects to /chat?oauth=success

 2.3 Account Service

 File: app/services/account_service.py (NEW)

 Methods:
 - get_account_token(db, account_id) → str
   - Fetch account, check expiration
   - Decrypt and return access token
 - get_primary_account(db, user_id) → Account | None
   - Get user's primary account (is_primary=True)
   - Fallback to first linked account

 2.4 Account Management Endpoints

 File: app/api/accounts.py (MODIFY)

 New Routes:
 - GET /api/v1/accounts/me → List[AccountResponse]
   - List user's linked accounts (ordered by is_primary)
 - POST /api/v1/accounts/{account_id}/set-primary
   - Set account as primary for current user
 - DELETE /api/v1/accounts/{account_id}/unlink
   - Unlink account from current user

 2.5 Instagram Client Updates

 File: app/clients/instagram_client.py (MODIFY)

 Changes:
 - Make settings parameter optional
 - Add access_token parameter (preferred)
 - Constructor logic:
 if access_token:
     self._token = access_token  # Per-account (preferred)
 elif settings:
     self._token = settings.instagram_page_access_token  # Legacy
 else:
     raise ValueError("Must provide access_token or settings")
 - Update all methods to use self._token instead of self._settings.instagram_page_access_token

 Usage Pattern:
 - New: InstagramClient(http_client, access_token=decrypted_token)
 - Legacy: InstagramClient(http_client, settings=settings) (backward compatible)

 Phase 3: UI Session & Context Updates

 3.1 Session Creation Update

 File: app/api/ui.py (MODIFY)

 Changes in POST /ui/session:
 - Fetch user's primary account: AccountService.get_primary_account(db, user.id)
 - Update JWT payload:
 payload = {
     "account_id": primary_account.id if primary_account else None,
     "user_id": user.id,
     "username": user.username,
     "exp": expiration_time,
     "type": "ui_session"
 }

 3.2 Conversations Endpoint Update

 File: app/api/ui.py (MODIFY)

 Changes in GET /ui/conversations:
 - Get primary account from user's linked accounts
 - Use primary_account.instagram_account_id instead of settings.instagram_business_account_id
 - Handle case where user has no linked accounts

 3.3 Message Sending Update

 File: app/api/messages.py (MODIFY)

 Changes in message sending:
 - Get account-specific token: AccountService.get_account_token(db, account_id)
 - Create InstagramClient with decrypted token:
 instagram_client = InstagramClient(http_client, access_token=access_token)

 Phase 4: Frontend Integration

 4.1 Accounts Store

 File: frontend/src/stores/accounts.js (NEW)

 State:
 - accounts (array of user's linked accounts)
 - loading, error

 Computed:
 - primaryAccount (account with is_primary=true)

 Actions:
 - fetchAccounts() - GET /api/v1/accounts/me
 - setPrimaryAccount(accountId) - POST /api/v1/accounts/{id}/set-primary
 - unlinkAccount(accountId) - DELETE /api/v1/accounts/{id}/unlink
 - startOAuthFlow() - Redirect to /oauth/instagram/authorize

 4.2 OAuth Login Button

 File: frontend/src/components/OAuthLoginButton.vue (NEW)

 Features:
 - Instagram gradient button ("Continue with Instagram")
 - Instagram icon (SVG)
 - Loading state
 - Calls accountsStore.startOAuthFlow() on click

 4.3 Account Switcher

 File: frontend/src/components/AccountSwitcher.vue (NEW)

 Features:
 - Dropdown showing current account (profile picture, username)
 - List of all linked accounts
 - "Primary" badge on primary account
 - "Link another Instagram account" button
 - Click account to set as primary (triggers page reload)

 4.4 Login View Update

 File: frontend/src/views/LoginView.vue (MODIFY)

 Changes:
 - Import OAuthLoginButton component
 - Add "Or" divider after password field
 - Add <OAuthLoginButton />

 4.5 Chat View Update

 File: frontend/src/views/ChatView.vue (MODIFY)

 Changes:
 - Import AccountSwitcher component
 - Add AccountSwitcher to header/sidebar
 - Fetch accounts on mount: accountsStore.fetchAccounts()

 Phase 5: Configuration & Environment

 5.1 Configuration Update

 File: app/config.py (MODIFY)

 New Settings:
 # Instagram OAuth
 self.instagram_oauth_client_id = os.getenv("INSTAGRAM_OAUTH_CLIENT_ID", "")
 self.instagram_oauth_client_secret = os.getenv("INSTAGRAM_OAUTH_CLIENT_SECRET", "")
 self.instagram_oauth_redirect_uri = os.getenv(
     "INSTAGRAM_OAUTH_REDIRECT_URI",
     f"{self.public_base_url}/oauth/instagram/callback"
 )

 5.2 Environment Variables

 File: .env.example (MODIFY)

 Add:
 # Instagram OAuth Configuration
 # Get from https://developers.facebook.com/apps/YOUR_APP_ID/settings/basic/
 INSTAGRAM_OAUTH_CLIENT_ID=your_facebook_app_id
 INSTAGRAM_OAUTH_CLIENT_SECRET=your_app_secret
 INSTAGRAM_OAUTH_REDIRECT_URI=http://localhost:8000/oauth/instagram/callback

 5.3 Route Registration

 File: app/main.py (MODIFY)

 Add:
 from app.api import oauth
 app.include_router(oauth.router, prefix="/oauth", tags=["oauth"])

 Phase 6: Migration & Deployment

 6.1 Data Migration Script

 File: scripts/migrate_existing_account.py (NEW)

 Purpose:
 - Migrate existing settings.instagram_business_account_id to database
 - Create Account record with Fernet-encrypted token
 - Link to first user in database (or create default admin user)
 - Set as primary account

 Run after Alembic migration:
 python scripts/migrate_existing_account.py

 6.2 Facebook App Configuration

 Steps:
 1. Go to https://developers.facebook.com/apps/YOUR_APP_ID
 2. Add Instagram product
 3. Configure OAuth Redirect URIs:
   - Development: http://localhost:8000/oauth/instagram/callback
   - Production: https://your-domain.com/oauth/instagram/callback
 4. Request instagram_manage_messages permission
 5. Submit app for review (required for production)

 6.3 Deployment Checklist

 Database:
 # Run migration
 .\venv\Scripts\python.exe -m alembic upgrade head

 # Migrate existing account
 python scripts/migrate_existing_account.py

 Environment Variables:
 - Add INSTAGRAM_OAUTH_CLIENT_ID
 - Add INSTAGRAM_OAUTH_CLIENT_SECRET
 - Add INSTAGRAM_OAUTH_REDIRECT_URI

 Frontend:
 cd frontend && npm run build

 Nginx (Production):
 # Add OAuth routes
 location /oauth/ {
     proxy_pass http://localhost:8000;
     proxy_set_header Host $host;
 }

 Implementation Sequence

 Week 1: Backend Foundation

 Days 1-2:
 - Create EncryptionService with Fernet
 - Update database models (UserAccount, OAuthState, enhanced User/Account)
 - Create and run Alembic migration
 - Test encryption service

 Days 3-4:
 - Implement OAuthService (authorization URL, token exchange)
 - Create OAuth API endpoints (/authorize, /callback)
 - Create AccountService (get_account_token, get_primary_account)
 - Update InstagramClient for per-account tokens

 Day 5:
 - Add account management endpoints (/accounts/me, /set-primary, /unlink)
 - Update UI session creation to use primary account
 - Update conversations/messages endpoints for per-account context

 Week 2: Frontend & Testing

 Days 6-7:
 - Create accounts Pinia store
 - Build OAuthLoginButton component
 - Build AccountSwitcher component
 - Update LoginView and ChatView

 Days 8-9:
 - Write unit tests (encryption, OAuth service)
 - Manual OAuth flow testing
 - Create migration script for existing account
 - Update documentation

 Day 10:
 - Deploy to staging
 - End-to-end testing
 - Production deployment

 Critical Files Summary

 NEW FILES (9)

 1. app/services/encryption_service.py - Fernet encryption
 2. app/services/oauth_service.py - OAuth flow logic
 3. app/services/account_service.py - Account operations
 4. app/api/oauth.py - OAuth endpoints
 5. alembic/versions/xxx_add_oauth_support.py - Database migration
 6. scripts/migrate_existing_account.py - Data migration
 7. frontend/src/stores/accounts.js - Accounts Pinia store
 8. frontend/src/components/OAuthLoginButton.vue - OAuth button
 9. frontend/src/components/AccountSwitcher.vue - Account switcher

 MODIFIED FILES (8)

 1. app/db/models.py - Add UserAccount, OAuthState, enhance User/Account
 2. app/config.py - Add OAuth configuration
 3. app/clients/instagram_client.py - Per-account token support
 4. app/api/accounts.py - Add account management endpoints
 5. app/api/ui.py - Update session and conversations for multi-account
 6. app/api/messages.py - Use per-account tokens
 7. app/main.py - Register OAuth router
 8. .env.example - Add OAuth environment variables
 9. frontend/src/views/LoginView.vue - Add OAuth button
 10. frontend/src/views/ChatView.vue - Add account switcher

 Key Design Decisions

 Security

 - Fernet encryption replaces base64 (AES-128 with HMAC authentication)
 - OAuth state tokens prevent CSRF attacks (10-minute expiration)
 - Long-lived tokens from Instagram (60-day expiration, tracked in DB)
 - Session secret reuse for encryption key derivation (no new config)

 Multi-Tenancy

 - Many-to-many user-account relationship (supports team collaboration)
 - Primary account concept for default selection
 - Role-based access (owner/admin/viewer) for future permissions

 Backward Compatibility

 - Optional access_token in InstagramClient (settings still works)
 - Nullable OAuth fields on User model (username/password users unaffected)
 - Migration script handles existing settings-based account

 Webhook Routing

 - No changes needed - already routes by recipient_id
 - Shared app secret - all users' accounts validated with same Instagram app
 - Post-validation routing - account lookup happens after signature check

 Success Criteria

 - ✅ Users can log in with Instagram OAuth
 - ✅ Users can link multiple Instagram accounts
 - ✅ Users can switch between accounts
 - ✅ Messages filtered by selected account
 - ✅ Webhooks routed correctly to account owners
 - ✅ Tokens encrypted with Fernet (not base64)
 - ✅ Existing account migrated successfully
 - ✅ Username/password login still works
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌

 Would you like to proceed?

 > 1. Yes, and auto-accept edits
   2. Yes, and manually approve edits
   3. Type here to tell Claude what to change