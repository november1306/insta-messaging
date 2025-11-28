
  Recommended Architecture

  Phase 1 (Now): Session-based authentication
  ┌─────────┐    1. GET /ui/session     ┌─────────┐
  │  Browser│ ──────────────────────────>│ Backend │
  │         │ (nginx basic auth)         │         │
  │         │<─────────────────────────── │         │
  │         │    session token (JWT)     └─────────┘
  │         │                                  │
  │         │    2. GET /ui/conversations     │
  │         │ ──────────────────────────────> │
  │         │  Authorization: Bearer <JWT>    │
  │         │    (includes account_id)        │
  └─────────┘                                  │
                                               ▼
                                      Validates JWT
                                      Loads account context

  Phase 2 (Future): Instagram OAuth
  User → Instagram OAuth → Backend creates JWT with account_id → Multi-tenant UI

  Implementation:

  1. Create session endpoint (Phase 1)

  # app/api/ui.py

  from datetime import datetime, timedelta
  import jwt

  @router.post("/ui/session")
  async def create_session(
      # Only accessible behind nginx basic auth
      account_id: str = settings.instagram_business_account_id
  ):
      """
      Create a UI session token.

      Phase 1: Uses default account (nginx auth protects this)
      Phase 2: Will use Instagram OAuth to determine account_id
      """
      # Create JWT with account context
      payload = {
          "account_id": account_id,
          "exp": datetime.utcnow() + timedelta(hours=24),
          "type": "ui_session"
      }

      token = jwt.encode(payload, settings.session_secret, algorithm="HS256")

      return {
          "token": token,
          "account_id": account_id,
          "expires_in": 86400  # 24 hours
      }

  2. Add session validation middleware

  # app/api/auth.py

  async def verify_ui_session(
      authorization: str = Header(None),
      db: AsyncSession = Depends(get_db_session)
  ):
      """Verify UI session token (JWT)"""
      if not authorization or not authorization.startswith("Bearer "):
          raise HTTPException(401, "Missing session token")

      token = authorization.replace("Bearer ", "")

      try:
          payload = jwt.decode(token, settings.session_secret, algorithms=["HS256"])

          if payload.get("type") != "ui_session":
              raise HTTPException(401, "Invalid token type")

          # Return account context
          return {"account_id": payload["account_id"]}

      except jwt.ExpiredSignatureError:
          raise HTTPException(401, "Session expired")
      except jwt.InvalidTokenError:
          raise HTTPException(401, "Invalid session token")

  3. Update UI endpoints to use session auth

  @router.get("/ui/conversations")
  async def get_conversations(
      session: dict = Depends(verify_ui_session),  # ← Changed from API key
      db: AsyncSession = Depends(get_db_session)
  ):
      account_id = session["account_id"]
      # Filter conversations by account_id
      # ... rest of implementation

  4. Update frontend to fetch session token

  // frontend/src/stores/session.js
  export const useSessionStore = defineStore('session', () => {
    const token = ref(null)
    const accountId = ref(null)

    async function createSession() {
      const response = await axios.post('/api/v1/ui/session')
      token.value = response.data.token
      accountId.value = response.data.account_id

      // Configure API client to use session token
      apiClient.defaults.headers.Authorization = `Bearer ${token.value}`
    }

    return { token, accountId, createSession }
  })

  Benefits of this approach:

  ✅ Secure: No API keys in frontend code
  ✅ Multi-tenant ready: JWT contains account_id for future multi-user support
  ✅ OAuth-ready: Easy to swap nginx auth for Instagram OAuth later
  ✅ API remains protected: Direct API calls still require API keys
  ✅ Flexible: Can add permissions, roles, etc. to JWT
  ✅ Standard: Industry best practice (JWT sessions)

  Migration Path:

  Now → Phase 2 (Instagram OAuth):
  1. Add Instagram OAuth endpoint: /auth/instagram/login
  2. User authenticates with Instagram
  3. Backend fetches their account info, creates JWT with their account_id
  4. UI shows only their conversations
  5. Remove nginx basic auth, use OAuth instead

  Want me to implement Phase 1 (session-based auth)?

> implement phase 1
  ⎿  5-hour limit reached · resets 3am (Europe/Kiev) ·
