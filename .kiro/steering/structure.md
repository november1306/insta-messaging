# Project Structure

## Directory Organization

```
instagram-messenger-automation/
├── app/                          # Main application code
│   ├── api/                      # API endpoints (FastAPI routers)
│   │   └── webhooks.py          # Instagram webhook handlers
│   ├── core/                     # Core domain logic
│   │   └── interfaces.py        # Abstract interfaces (IMessageRepository, etc.)
│   ├── db/                       # Database layer
│   │   ├── models.py            # SQLAlchemy ORM models
│   │   └── connection.py        # Database session management
│   ├── repositories/             # Data access implementations
│   │   └── message_repository.py
│   ├── config.py                # Configuration management
│   ├── main.py                  # Application entry point
│   └── __init__.py
├── tests/                        # Test suite
│   ├── api/                     # API endpoint tests
│   ├── repositories/            # Repository integration tests
│   ├── conftest.py              # Pytest fixtures and configuration
│   └── __init__.py
├── alembic/                      # Database migrations
│   ├── versions/                # Migration scripts
│   ├── env.py                   # Alembic environment config
│   └── script.py.mako           # Migration template
├── docs/                         # Documentation (HTML)
├── .kiro/                        # Kiro IDE configuration
│   ├── specs/                   # Feature specifications
│   └── steering/                # AI assistant guidance (this file)
├── .env                          # Environment variables (not in git)
├── .env.example                 # Environment template
├── alembic.ini                  # Alembic configuration
├── requirements.txt             # Python dependencies
├── environment.yml              # Conda environment definition
├── README.md                    # Project documentation
├── ARCHITECTURE.md              # Architecture overview
└── SETUP.md                     # Setup instructions
```

## Key Conventions

### Module Organization
- **app/api/**: FastAPI routers, one file per resource/domain
- **app/core/**: Domain models and interfaces (abstract base classes)
- **app/repositories/**: Concrete implementations of data access interfaces
- **app/db/**: Database models and connection management

### Naming Patterns
- **Interfaces**: Prefix with `I` (e.g., `IMessageRepository`)
- **Domain Models**: Plain classes without suffix (e.g., `Message`)
- **ORM Models**: Suffix with `Model` (e.g., `MessageModel`)
- **Repositories**: Suffix with `Repository` (e.g., `MessageRepository`)

### Import Conventions
- Use absolute imports from `app` package
- Example: `from app.core.interfaces import Message`
- Example: `from app.repositories.message_repository import MessageRepository`

### Configuration
- Environment variables loaded via `python-dotenv` from `.env` file
- Configuration centralized in `app/config.py` as `Settings` class
- Access via `from app.config import settings`

### Database
- SQLAlchemy async sessions via `get_db_session()` dependency
- Alembic for schema migrations
- SQLite for development, MySQL for production (target)
- Database file: `instagram_automation.db` (gitignored)

### Testing
- Integration tests in `tests/` mirror `app/` structure
- Pytest with async support (`pytest-asyncio`)
- Database fixture in `conftest.py` provides clean state per test
- Test files prefixed with `test_`

### Logging
- Standard Python logging module
- Logger per module: `logger = logging.getLogger(__name__)`
- Log levels: INFO for normal operations, ERROR for failures
- Never log message content or personal data (privacy)

## Architecture Patterns

### Interface-Driven Design
- Define interfaces in `app/core/interfaces.py`
- Implement in `app/repositories/` or other concrete modules
- Enables testing with mocks and future implementation swaps

### Repository Pattern
- Repositories handle data access and ORM conversion
- Convert between domain models (e.g., `Message`) and ORM models (e.g., `MessageModel`)
- Repositories injected via FastAPI dependency injection

### Async/Await
- All database operations are async
- FastAPI endpoints are async
- Use `async def` and `await` consistently

### Dependency Injection
- FastAPI's `Depends()` for database sessions
- Example: `db: AsyncSession = Depends(get_db_session)`
- Session lifecycle managed automatically (commit/rollback)

## YAGNI Principle

The codebase follows "You Aren't Gonna Need It" - start minimal, add complexity only when needed. Comments in code often reference YAGNI to explain why simpler approaches were chosen.
