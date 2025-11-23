# Design Document

## Overview

Simple dual storage: write messages to both local SQLite (for the app) and CRM MySQL (for CRM display). CRM writes are best-effort - if they fail, log it and move on.

**Key Principle:** CRM failures don't break anything. Local SQLite is the source of truth.

### Data Flow

1. Save message to local SQLite (must succeed)
2. Try to save to CRM MySQL (best-effort, don't wait)
3. If CRM fails: log error, continue
4. Return success

## Architecture

**Simple approach:**
- Modify existing `MessageRepository.save()` to write to both databases
- Use `aiomysql` for CRM MySQL connection
- Wrap CRM write in try/except - log errors, don't raise

## Implementation

### Modified MessageRepository

Add CRM sync directly to existing `MessageRepository.save()`:

```python
class MessageRepository(IMessageRepository):
    def __init__(self, db_session: AsyncSession, crm_pool=None):
        self._db = db_session
        self._crm_pool = crm_pool  # aiomysql connection pool
    
    async def save(self, message: Message) -> Message:
        # 1. Save to local SQLite (must succeed)
        db_message = MessageModel(...)
        self._db.add(db_message)
        await self._db.flush()
        
        # 2. Try CRM sync (best-effort, don't block)
        if self._crm_pool:
            asyncio.create_task(self._sync_to_crm(message))
        
        return message
    
    async def _sync_to_crm(self, message: Message):
        try:
            async with self._crm_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    # Map fields
                    user_id = message.sender_id if message.direction == 'inbound' else message.recipient_id
                    direction = 'in' if message.direction == 'inbound' else 'out'
                    
                    # Insert
                    await cur.execute(
                        "INSERT INTO messages (user_id, username, direction, message, created_at) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (user_id, user_id, direction, message.message_text, message.timestamp)
                    )
                    await conn.commit()
                    
            logger.info(f"CRM sync OK: {message.id}")
        except Exception as e:
            # TODO: CRM table missing fields (instagram_message_id, sender/recipient, conversation_id, status)
            logger.error(f"CRM sync failed: {e}")
```

### Configuration

Add to `.env`:
```bash
CRM_MYSQL_ENABLED=true
CRM_MYSQL_HOST=mysql314.1gb.ua
CRM_MYSQL_USER=gbua_zag
CRM_MYSQL_PASSWORD=az3abdc5z2
CRM_MYSQL_DATABASE=gbua_zag
```

Add to `app/config.py`:
```python
class Settings(BaseSettings):
    crm_mysql_enabled: bool = False
    crm_mysql_host: str = "mysql314.1gb.ua"
    crm_mysql_user: str = ""
    crm_mysql_password: str = ""
    crm_mysql_database: str = "gbua_zag"
```

### Startup

Create CRM pool in `app/main.py`:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create CRM pool if enabled
    crm_pool = None
    if settings.crm_mysql_enabled:
        try:
            crm_pool = await aiomysql.create_pool(
                host=settings.crm_mysql_host,
                user=settings.crm_mysql_user,
                password=settings.crm_mysql_password,
                db=settings.crm_mysql_database,
                minsize=1,
                maxsize=5
            )
            logger.info("CRM MySQL connected")
        except Exception as e:
            logger.error(f"CRM MySQL failed: {e}")
    
    app.state.crm_pool = crm_pool
    yield
    
    if crm_pool:
        crm_pool.close()
        await crm_pool.wait_closed()
```

## Field Mapping

**Local → CRM:**
- `sender_id` (inbound) or `recipient_id` (outbound) → `user_id`
- `sender_id` → `username` (fallback to user_id)
- `'inbound'` → `'in'`, `'outbound'` → `'out'`
- `message_text` → `message`
- `timestamp` → `created_at`

**CRM table (external, don't modify):**
```sql
CREATE TABLE messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(100),
    username VARCHAR(100),
    direction ENUM('in','out'),
    message TEXT,
    created_at TIMESTAMP
);
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Local storage determines success

*For any* message, save() returns success if and only if local SQLite save succeeds, regardless of CRM status.

**Validates: Requirements 1.1, 1.2, 2.3**

### Property 2: CRM failures don't raise exceptions

*For any* message, CRM MySQL failures should not raise exceptions from save().

**Validates: Requirements 2.2, 2.4**

### Property 3: Direction mapping

*For any* message, 'inbound' maps to 'in' and 'outbound' maps to 'out'.

**Validates: Requirements 4.3**

## Error Handling

All CRM errors are logged but don't stop processing:

```python
try:
    # CRM sync
except Exception as e:
    # TODO: CRM table missing fields (instagram_message_id, sender/recipient, conversation_id, status)
    logger.error(f"CRM sync failed: {e}")
```

## Testing Strategy

**Manual testing:**
1. Save message with CRM enabled → check both databases
2. Save message with CRM disabled → check local only
3. Save message with CRM down → verify local works, error logged

**Optional unit tests:**
- Test direction mapping ('inbound' → 'in', 'outbound' → 'out')
- Test CRM failure doesn't raise exception

## Deployment

**Dependencies:**
```bash
pip install aiomysql
```

**Configuration (.env):**
```bash
CRM_MYSQL_ENABLED=true
CRM_MYSQL_HOST=mysql314.1gb.ua
CRM_MYSQL_USER=gbua_zag
CRM_MYSQL_PASSWORD=az3abdc5z2
CRM_MYSQL_DATABASE=gbua_zag
```

**Rollback:**
Set `CRM_MYSQL_ENABLED=false` to disable
