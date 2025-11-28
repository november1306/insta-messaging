# JWT Authentication Implementation Plan

## Overview
Implement proper JWT authentication with Basic Auth credential validation on the backend.

## Authentication Flow

```
┌─────────┐                 ┌─────────┐                 ┌─────────┐
│ Browser │                 │  Nginx  │                 │ Backend │
└────┬────┘                 └────┬────┘                 └────┬────┘
     │                           │                           │
     │  1. GET /chat            │                           │
     ├──────────────────────────>│                           │
     │                           │                           │
     │  2. Return HTML/JS       │                           │
     │<──────────────────────────┤                           │
     │                           │                           │
     │  3. User enters username/password in login form       │
     │                           │                           │
     │  4. POST /ui/session      │                           │
     │     Authorization: Basic base64(username:password)    │
     ├──────────────────────────>│──────────────────────────>│
     │                           │                           │
     │                           │  5. Validate credentials  │
     │                           │     (check DB, verify     │
     │                           │      bcrypt password)     │
     │                           │                           │
     │                           │  6. Generate JWT token    │
     │                           │                           │
     │  7. Return JWT token      │                           │
     │<──────────────────────────┴───────────────────────────┤
     │     {token: "eyJ...", account_id: "123", expires_in}  │
     │                           │                           │
     │  8. Store JWT in localStorage                         │
     │                           │                           │
     │  9. GET /ui/conversations │                           │
     │     Authorization: Bearer eyJ...                      │
     ├──────────────────────────>│──────────────────────────>│
     │                           │                           │
     │                           │  10. Validate JWT token   │
     │                           │                           │
     │  11. Return data          │                           │
     │<──────────────────────────┴───────────────────────────┤
     │                           │                           │
```

## Implementation Tasks

### 1. Database Schema
**File:** `alembic/versions/xxx_add_users_table.py`

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on username for faster lookups
CREATE INDEX idx_users_username ON users(username);
```

**Fields:**
- `username`: Unique username for login (e.g., "admin")
- `password_hash`: Bcrypt hashed password
- `is_active`: Allow disabling users without deleting
- `created_at`, `updated_at`: Audit timestamps

### 2. Backend Models
**File:** `app/db/models.py`

Add User model:
```python
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc))
```

### 3. User Service
**File:** `app/services/user_service.py` (new file)

```python
class UserService:
    @staticmethod
    async def create_user(db: AsyncSession, username: str, password: str) -> User:
        """Create a new user with bcrypt hashed password"""

    @staticmethod
    async def validate_credentials(db: AsyncSession, username: str, password: str) -> Optional[User]:
        """Validate username/password, return User if valid"""

    @staticmethod
    async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
        """Get user by username"""

    @staticmethod
    async def update_password(db: AsyncSession, user_id: int, new_password: str) -> bool:
        """Update user password"""

    @staticmethod
    async def deactivate_user(db: AsyncSession, user_id: int) -> bool:
        """Deactivate user (soft delete)"""
```

### 4. Update Session Endpoint
**File:** `app/api/ui.py`

Update `POST /ui/session`:
```python
@router.post("/ui/session")
async def create_session(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Create a UI session token (JWT) by validating Basic Auth credentials.

    Expects: Authorization: Basic <base64(username:password)>
    Returns: JWT token for subsequent requests
    """
    # Extract Basic Auth credentials
    if not authorization or not authorization.startswith("Basic "):
        raise HTTPException(401, "Missing Basic Auth credentials")

    # Decode base64 credentials
    credentials = decode_basic_auth(authorization)

    # Validate against database
    user = await UserService.validate_credentials(db, credentials.username, credentials.password)

    if not user:
        raise HTTPException(401, "Invalid username or password")

    if not user.is_active:
        raise HTTPException(401, "User account is disabled")

    # Generate JWT token (existing logic)
    # ... create and return JWT
```

### 5. User Management Endpoints
**File:** `app/api/users.py` (new file)

```python
# Create user (protected by JWT - only authenticated users can create users)
POST /api/v1/users
  Headers: Authorization: Bearer <jwt_token>
  Body: {username: "newuser", password: "password123"}

# Change own password
PUT /api/v1/users/me/password
  Headers: Authorization: Bearer <jwt_token>
  Body: {current_password: "old", new_password: "new"}

# List users (admin only)
GET /api/v1/users
  Headers: Authorization: Bearer <jwt_token>

# Deactivate user (admin only)
DELETE /api/v1/users/{username}
  Headers: Authorization: Bearer <jwt_token>
```

### 6. CLI Command for User Management
**File:** `app/cli/user_management.py` (new file)

```bash
# Create first user (for fresh deployment)
python -m app.cli.user_management create-user --username admin --password SecurePass123

# Create user interactively
python -m app.cli.user_management create-user --interactive

# Change password
python -m app.cli.user_management change-password --username admin

# List users
python -m app.cli.user_management list-users

# Deactivate user
python -m app.cli.user_management deactivate-user --username olduser
```

### 7. Deployment Script Updates
**File:** `deploy-production.sh`

**Remove nginx basic auth for `/ui/*` endpoints:**
```nginx
# OLD - Remove this:
location ~ ^/(chat|ui) {
    auth_basic "Instagram Chat - Login Required";
    auth_basic_user_file /etc/nginx/.htpasswd;
    ...
}

# NEW - No auth on nginx, backend handles it:
location ~ ^/(chat|ui) {
    proxy_pass http://127.0.0.1:8000;
    ...
}
```

**Add user creation during deployment:**
```bash
echo -e "${GREEN}[X/13] Creating default admin user...${NC}"

# Check if any users exist
USER_COUNT=$(sudo -u ${APP_USER} ${INSTALL_DIR}/venv/bin/python -c "
from app.db.connection import get_db_engine
from app.db.models import User
from sqlalchemy import select, func
import asyncio

async def count_users():
    engine = get_db_engine()
    async with engine.begin() as conn:
        result = await conn.execute(select(func.count(User.id)))
        return result.scalar()

print(asyncio.run(count_users()))
")

if [ "$USER_COUNT" -eq 0 ]; then
    echo "No users found. Creating default admin user..."

    # Prompt for admin password or generate random one
    read -p "Enter admin password (leave empty to generate random): " ADMIN_PASSWORD

    if [ -z "$ADMIN_PASSWORD" ]; then
        ADMIN_PASSWORD=$($PYTHON_BIN -c "import secrets; print(secrets.token_urlsafe(16))")
        echo "Generated admin password: $ADMIN_PASSWORD"
        echo "⚠️  SAVE THIS PASSWORD - It will not be shown again!"
    fi

    # Create admin user
    sudo -u ${APP_USER} ${INSTALL_DIR}/venv/bin/python -m app.cli.user_management create-user \
        --username admin \
        --password "$ADMIN_PASSWORD"

    echo "✓ Admin user created: username=admin"
else
    echo "Users already exist (count: $USER_COUNT), skipping user creation"
fi
```

### 8. Frontend Changes
**File:** `frontend/src/views/LoginView.vue` (new file)

Create login form:
```vue
<template>
  <div class="login-container">
    <form @submit.prevent="handleLogin">
      <h1>Instagram Chat Login</h1>
      <input v-model="username" type="text" placeholder="Username" required>
      <input v-model="password" type="password" placeholder="Password" required>
      <button type="submit">Login</button>
      <div v-if="error" class="error">{{ error }}</div>
    </form>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '../stores/session'

const sessionStore = useSessionStore()
const router = useRouter()

const username = ref('')
const password = ref('')
const error = ref(null)

async function handleLogin() {
  try {
    await sessionStore.login(username.value, password.value)
    router.push('/chat')
  } catch (err) {
    error.value = 'Invalid username or password'
  }
}
</script>
```

**File:** `frontend/src/stores/session.js`

Update session store to send Basic Auth:
```javascript
async function login(username, password) {
  loading.value = true
  error.value = null

  try {
    // Encode credentials as Basic Auth
    const credentials = btoa(`${username}:${password}`)

    // Call session endpoint with Basic Auth
    const response = await apiClient.post('/ui/session', null, {
      headers: {
        'Authorization': `Basic ${credentials}`
      }
    })

    if (response.data.error || !response.data.token) {
      throw new Error(response.data.error || 'Failed to create session')
    }

    // Store session data (same as before)
    token.value = response.data.token
    accountId.value = response.data.account_id
    // ... rest of existing logic

  } catch (err) {
    error.value = err.message || 'Invalid credentials'
    throw err
  } finally {
    loading.value = false
  }
}
```

**File:** `frontend/src/router/index.js`

Add login route and auth guard:
```javascript
const routes = [
  {
    path: '/login',
    name: 'login',
    component: LoginView
  },
  {
    path: '/chat',
    name: 'chat',
    component: ChatView,
    meta: { requiresAuth: true }
  }
]

router.beforeEach((to, from, next) => {
  const sessionStore = useSessionStore()

  if (to.meta.requiresAuth && !sessionStore.isAuthenticated) {
    next('/login')
  } else if (to.path === '/login' && sessionStore.isAuthenticated) {
    next('/chat')
  } else {
    next()
  }
})
```

### 9. Configuration Changes
**File:** `app/config.py`

Remove hardcoded SESSION_SECRET default:
```python
# JWT/Session configuration for UI authentication
if self.environment == "production":
    self.session_secret = self._get_required("SESSION_SECRET")
else:
    # Development: Generate random secret on startup if not provided
    session_secret_env = os.getenv("SESSION_SECRET", "")
    if session_secret_env:
        self.session_secret = session_secret_env
    else:
        import secrets
        self.session_secret = secrets.token_urlsafe(32)
        import logging
        logging.getLogger(__name__).warning(
            "⚠️  No SESSION_SECRET provided - generated random secret for this session. "
            "JWT tokens will not persist across restarts. Set SESSION_SECRET in .env for persistent tokens."
        )
```

**File:** `.env.example`

Add example:
```bash
# Session/JWT Configuration
SESSION_SECRET=your_session_secret_here  # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
```

## Fresh Deployment Flow

1. Run deployment script
2. Script detects no users in database
3. Script prompts: "Enter admin password (or press Enter to generate random)"
4. Script creates admin user with bcrypt hashed password
5. Script displays credentials (if generated)
6. Admin can now login via UI
7. Admin can create additional users via API or CLI

## Redeployment Flow

1. Run deployment script
2. Script detects existing users in database
3. Script skips user creation
4. Existing users continue working
5. No manual intervention needed

## Security Considerations

1. **Password Storage**: Bcrypt hashed (cost factor 12)
2. **JWT Secret**: Required in production, generated in development
3. **HTTPS**: Should use SSL in production (passwords in transit)
4. **Token Expiration**: Configurable (default 24 hours)
5. **No nginx basic auth**: Backend handles all authentication
6. **Database**: SQLite file must be protected (file permissions)

## Migration Path

For existing deployments:
1. Run database migration to create users table
2. Run CLI command to create first user
3. Update nginx config (remove basic auth from `/ui/*`)
4. Restart nginx and application
5. Frontend will show login form
6. Users login with new credentials

## User Management Best Practices

1. **First User**: Created via CLI during deployment
2. **Additional Users**: Created by existing users via API
3. **Password Changes**: Users can change their own password
4. **User Deactivation**: Soft delete (set is_active=False)
5. **Audit Trail**: created_at, updated_at timestamps
