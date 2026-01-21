#!/bin/bash
# Verify local development setup for the hybrid approach

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "============================================================"
echo "  Local Development Setup Verification"
echo "============================================================"
echo ""

# Track overall status
ALL_OK=true

# 1. Check data directory exists
echo -n "1. Checking data/ directory... "
if [ -d "data" ]; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}MISSING${NC}"
    echo "   Create with: mkdir -p data"
    ALL_OK=false
fi

# 2. Check local database exists
echo -n "2. Checking local database copy... "
if [ -f "data/local-copy.db" ]; then
    SIZE=$(du -h "data/local-copy.db" | cut -f1)
    echo -e "${GREEN}OK${NC} ($SIZE)"
else
    echo -e "${YELLOW}NOT FOUND${NC}"
    echo "   Copy from VPS: scp root@185.156.43.172:/opt/insta-messaging/data/production.db ./data/local-copy.db"
fi

# 3. Check .env file exists
echo -n "3. Checking .env file... "
if [ -f ".env" ]; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}MISSING${NC}"
    echo "   Create with: cp .env.example .env"
    ALL_OK=false
fi

# 4. Check DATABASE_URL points to local copy (if using hybrid approach)
echo -n "4. Checking DATABASE_URL... "
if [ -f ".env" ]; then
    DB_URL=$(grep "^DATABASE_URL=" .env 2>/dev/null | cut -d= -f2-)
    if [ -z "$DB_URL" ]; then
        echo -e "${YELLOW}NOT SET${NC}"
    elif [[ "$DB_URL" == *"local-copy.db"* ]]; then
        echo -e "${GREEN}OK${NC} (using local copy)"
    elif [[ "$DB_URL" == *"instagram_automation.db"* ]]; then
        echo -e "${YELLOW}DEFAULT${NC} (using development DB)"
    else
        echo -e "${YELLOW}CUSTOM${NC}: $DB_URL"
    fi
else
    echo -e "${YELLOW}SKIPPED${NC} (no .env file)"
fi

# 5. Check SESSION_SECRET is set
echo -n "5. Checking SESSION_SECRET... "
if [ -f ".env" ]; then
    SECRET=$(grep "^SESSION_SECRET=" .env 2>/dev/null | cut -d= -f2-)
    if [ -z "$SECRET" ] || [ "$SECRET" = "your_session_secret_here" ]; then
        echo -e "${RED}NOT SET${NC}"
        echo "   CRITICAL: Must match production to decrypt OAuth tokens!"
        echo "   Get from VPS: ssh root@185.156.43.172 \"grep SESSION_SECRET /opt/insta-messaging/.env\""
        ALL_OK=false
    else
        echo -e "${GREEN}OK${NC}"
    fi
else
    echo -e "${YELLOW}SKIPPED${NC} (no .env file)"
fi

# 6. Check INSTAGRAM_APP_SECRET is set
echo -n "6. Checking INSTAGRAM_APP_SECRET... "
if [ -f ".env" ]; then
    SECRET=$(grep "^INSTAGRAM_APP_SECRET=" .env 2>/dev/null | cut -d= -f2-)
    if [ -z "$SECRET" ] || [ "$SECRET" = "your_instagram_app_secret_here" ]; then
        echo -e "${YELLOW}NOT SET${NC}"
        echo "   Needed for webhook signature validation"
        echo "   Get from VPS: ssh root@185.156.43.172 \"grep INSTAGRAM_APP_SECRET /opt/insta-messaging/.env\""
    else
        echo -e "${GREEN}OK${NC}"
    fi
else
    echo -e "${YELLOW}SKIPPED${NC} (no .env file)"
fi

# 7. Check virtual environment
echo -n "7. Checking Python virtual environment... "
if [ -d "venv" ] && [ -f "venv/bin/python" ]; then
    PY_VERSION=$(./venv/bin/python --version 2>&1)
    echo -e "${GREEN}OK${NC} ($PY_VERSION)"
else
    echo -e "${RED}MISSING${NC}"
    echo "   Create with: python3 -m venv venv && ./venv/bin/pip install -r requirements.txt"
    ALL_OK=false
fi

# 8. Check WebhookSimulator utility exists
echo -n "8. Checking WebhookSimulator utility... "
if [ -f "app/utils/webhook_simulator.py" ]; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}MISSING${NC}"
    echo "   Required for /test-webhook skill"
    ALL_OK=false
fi

# 9. Check if backend is running
echo -n "9. Checking if backend is running... "
BACKEND_STATUS=$(timeout 3 curl -s --connect-timeout 2 -o /dev/null -w "%{http_code}" http://localhost:8000/docs 2>/dev/null || echo "000")
if [ "$BACKEND_STATUS" = "200" ]; then
    echo -e "${GREEN}OK${NC} (port 8000)"
else
    echo -e "${YELLOW}NOT RUNNING${NC}"
    echo "   Start with: ./scripts/linux/dev-all.sh"
fi

# 10. Check if frontend is running
echo -n "10. Checking if frontend is running... "
FRONTEND_STATUS=$(timeout 3 curl -s --connect-timeout 2 -o /dev/null -w "%{http_code}" http://localhost:5173/ 2>/dev/null || echo "000")
if [ "$FRONTEND_STATUS" = "200" ]; then
    echo -e "${GREEN}OK${NC} (port 5173)"
else
    echo -e "${YELLOW}NOT RUNNING${NC}"
    echo "   Start with: ./scripts/linux/dev-all.sh"
fi

# Summary
echo ""
echo "============================================================"
if [ "$ALL_OK" = true ]; then
    echo -e "  ${GREEN}Setup verification complete!${NC}"
    echo ""
    echo "  Next steps:"
    echo "  1. Start services: ./scripts/linux/dev-all.sh"
    echo "  2. Open UI: http://localhost:5173/chat/"
    echo "  3. Test webhook: /test-webhook --message \"Hello\""
else
    echo -e "  ${RED}Some checks failed. Fix issues above.${NC}"
fi
echo "============================================================"
