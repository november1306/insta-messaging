# Data Directory

This directory stores local database copies for development.

## Usage

Copy production database for local development:

```bash
scp root@185.156.43.172:/opt/insta-messaging/data/production.db ./data/local-copy.db
```

Then update your `.env` to use it:

```bash
DATABASE_URL=sqlite+aiosqlite:///./data/local-copy.db
```

**Important**: `SESSION_SECRET` in your local `.env` must match production to decrypt OAuth access tokens stored in the database.

## Files

- `local-copy.db` - Copy of production database (gitignored)
- `test.db` - Clean test database (gitignored)

## Why Copy Production DB?

Instagram OAuth can only be completed on production (requires public HTTPS domain for callbacks). By copying the production database:

1. You get fully authenticated Instagram accounts with valid tokens
2. You can develop and test locally without needing OAuth flow
3. Outbound messages actually send to Instagram (if tokens are valid)

## Refreshing Database

If tokens expire or accounts change, re-copy from production:

```bash
scp root@185.156.43.172:/opt/insta-messaging/data/production.db ./data/local-copy.db
```
