# Instagram Messenger Automation

Automated Instagram DM response system for e-commerce businesses.

## Overview

This system receives customer messages via Instagram Direct Messages through Facebook's webhook callbacks and automatically responds based on predefined rules.

## Tech Stack

- **Backend**: Python with FastAPI
- **Database**: PostgreSQL
- **Deployment**: Railway or custom Linux server
- **Local Development**: Windows with ngrok for webhook tunneling

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Facebook App with Instagram permissions
- ngrok (for local development)

### Installation

```bash
# Clone the repository
git clone https://github.com/november1306/insta-messaging.git
cd insta-messaging

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your credentials

# Run the server
uvicorn app.main:app --reload
```

### Environment Variables

```
FACEBOOK_APP_ID=your-app-id
FACEBOOK_APP_SECRET=your-app-secret
FACEBOOK_VERIFY_TOKEN=your-verify-token
INSTAGRAM_PAGE_ACCESS_TOKEN=your-page-token
INSTAGRAM_PAGE_ID=your-page-id
DATABASE_URL=postgresql://...
```

## Development Status

🚧 **In Development** - Currently implementing Phase 1: Minimal Viable Solution

See [tasks.md](.kiro/specs/instagram-messenger-automation/tasks.md) for implementation progress.

## Documentation

- [Requirements](.kiro/specs/instagram-messenger-automation/requirements.md)
- [Design](.kiro/specs/instagram-messenger-automation/design.md)
- [Tasks](.kiro/specs/instagram-messenger-automation/tasks.md)

## License

See [LICENSE](LICENSE) file for details.
