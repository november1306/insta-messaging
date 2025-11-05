# Technology Stack

## Core Technologies

- **Language**: Python 3.12+
- **Web Framework**: FastAPI (async support)
- **Database**: SQLite (development), MySQL (production target)
- **ORM**: SQLAlchemy 2.0 with async support
- **Migrations**: Alembic
- **Security**: Cryptography library for credential encryption
- **Environment**: Miniconda/Anaconda for dependency management

## Key Dependencies

```
fastapi==0.115.6
uvicorn[standard]==0.32.0
sqlalchemy==2.0.23
aiosqlite==0.19.0
alembic==1.12.1
pydantic==2.5.0
httpx==0.27.2
pytest==8.3.5
pytest-asyncio==1.2.0
```

## Common Commands

### Environment Setup
```bash
# Create conda environment
conda env create -f environment.yml

# Activate environment
conda activate insta-auto

# Install dependencies (if not using conda)
pip install -r requirements.txt
```

### Database Management
```bash
# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Rollback migration
alembic downgrade -1
```

### Development Server
```bash
# Start FastAPI server with auto-reload
uvicorn app.main:app --reload

# Start on specific host/port
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Alternative: Use Python module syntax
python -m uvicorn app.main:app --reload
```

### Testing
```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/repositories/test_message_repository.py

# Run with coverage
pytest --cov=app
```

### Local Webhook Testing
```bash
# Start ngrok tunnel (separate terminal)
ngrok http 8000

# Test message sending
python test_send_message.py "@username" "Test message"
```

## Build System

No build step required - Python is interpreted. The application runs directly with uvicorn.

## Platform Notes

- **Development**: Windows with cmd/PowerShell
- **Production**: Linux server or Railway platform
- **Webhook Testing**: ngrok for local HTTPS tunneling
