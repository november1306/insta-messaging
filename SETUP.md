# Instagram Messenger Automation - Setup Guide

## Prerequisites

- **Miniconda or Anaconda** installed
- **Git** for version control
- **ngrok** (for local webhook testing)

## Environment Setup

### 1. Create Conda Environment

```bash
# Create environment from environment.yml
conda env create -f environment.yml

# Activate the environment
conda activate insta-auto
```

### 2. Verify Installation

```bash
# Check Python version
python --version  # Should be 3.12.x

# Check installed packages
conda list
```

### 3. Configure Environment Variables

Copy the example environment file and fill in your credentials:

```bash
# Copy example file
copy .env.example .env  # Windows
# or
cp .env.example .env    # Linux/Mac
```

Edit `.env` and add your credentials:

```env
# Facebook/Instagram Credentials
FACEBOOK_VERIFY_TOKEN=your_verify_token_here
FACEBOOK_APP_SECRET=your_app_secret_here
INSTAGRAM_PAGE_ACCESS_TOKEN=your_page_access_token_here

# Security
APP_SECRET_KEY=your-secret-key-for-encryption

# Environment
ENVIRONMENT=development

# Server
HOST=0.0.0.0
PORT=8000

# Logging
LOG_LEVEL=INFO
```

### 4. Initialize Database

```bash
# Run migrations to create database tables
alembic upgrade head
```

This creates `instagram_automation.db` with all required tables.

### 5. Start the Server

```bash
# Development mode with auto-reload
uvicorn app.main:app --reload

# Or specify host and port
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The server will be available at: http://localhost:8000

### 6. Verify Setup

Open your browser or use curl:

```bash
# Check root endpoint
curl http://localhost:8000

# Check health endpoint
curl http://localhost:8000/health

# Check webhook endpoint (should return 403 without proper params)
curl http://localhost:8000/webhooks/instagram
```

## Local Webhook Testing with ngrok

### 1. Install ngrok

Download from: https://ngrok.com/download

### 2. Start ngrok Tunnel

```bash
# Start tunnel to your local server
ngrok http 8000
```

You'll get a public URL like: `https://abc123.ngrok.io`

### 3. Configure Facebook Webhook

1. Go to your Facebook App Dashboard
2. Navigate to Webhooks section
3. Add webhook URL: `https://abc123.ngrok.io/webhooks/instagram`
4. Set verify token (same as `FACEBOOK_VERIFY_TOKEN` in .env)
5. Subscribe to `messages` events

## Updating the Environment

### Add New Package

```bash
# Using conda
conda install package-name

# Using pip (for packages not in conda)
pip install package-name

# Update environment.yml
conda env export --no-builds > environment.yml
```

### Update Existing Environment

```bash
# Update from environment.yml
conda env update -f environment.yml --prune
```

### Remove Environment

```bash
# Deactivate first
conda deactivate

# Remove environment
conda env remove -n insta-auto
```

## Database Management

### Create New Migration

After modifying models in `app/models/models.py`:

```bash
# Generate migration
alembic revision --autogenerate -m "Description of changes"

# Apply migration
alembic upgrade head
```

### Rollback Migration

```bash
# Rollback one version
alembic downgrade -1

# Rollback to specific version
alembic downgrade <revision_id>

# Rollback all
alembic downgrade base
```

### View Migration History

```bash
# Show current version
alembic current

# Show migration history
alembic history
```

## Troubleshooting

### Port Already in Use

```bash
# Windows: Find process using port 8000
netstat -ano | findstr :8000

# Kill the process
taskkill /PID <process_id> /F
```

### Database Locked Error

```bash
# Stop the server
# Delete the database file
del instagram_automation.db  # Windows
rm instagram_automation.db   # Linux/Mac

# Recreate database
alembic upgrade head
```

### Import Errors

```bash
# Make sure environment is activated
conda activate insta-auto

# Reinstall dependencies
conda env update -f environment.yml --prune
```

### ngrok Connection Issues

```bash
# Check if server is running
curl http://localhost:8000/health

# Restart ngrok
# Make sure to update webhook URL in Facebook if ngrok URL changed
```

## Production Deployment

### Switch to MySQL

Update `.env` for production:

```env
ENVIRONMENT=production
MYSQL_HOST=your-mysql-host
MYSQL_PORT=3306
MYSQL_DATABASE=instagram_automation
MYSQL_USERNAME=your-username
MYSQL_PASSWORD=your-password
```

### Run Migrations on Production

```bash
# Set production environment
export ENVIRONMENT=production  # Linux/Mac
set ENVIRONMENT=production     # Windows

# Run migrations
alembic upgrade head
```

## Development Workflow

1. **Activate environment**: `conda activate insta-auto`
2. **Start server**: `uvicorn app.main:app --reload`
3. **Start ngrok**: `ngrok http 8000` (in another terminal)
4. **Make changes**: Edit code, server auto-reloads
5. **Test**: Send test messages via Instagram
6. **Check logs**: View terminal output

## Useful Commands

```bash
# Activate environment
conda activate insta-auto

# Deactivate environment
conda deactivate

# List environments
conda env list

# List packages
conda list

# Start server
uvicorn app.main:app --reload

# Run migrations
alembic upgrade head

# Start ngrok
ngrok http 8000
```

## Next Steps

- Configure Instagram Business Account in Facebook App Dashboard
- Set up webhook subscriptions
- Add response rules to database
- Test with real Instagram messages
- Deploy to production (Railway, Heroku, or custom server)
