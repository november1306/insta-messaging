#!/bin/bash
# Error Checking Script for Test Environment
# Usage: ./scripts/check-errors.sh [hours_to_check]

# Colors
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Default to checking last 24 hours
HOURS=${1:-24}

echo "======================================"
echo "🔍 Error Analysis Report"
echo "======================================"
echo "Checking logs from last $HOURS hours"
echo ""

# Check if running on server or need to SSH
if [ -f "/opt/insta-messaging/.env" ]; then
    # Running on server
    LOG_CMD="journalctl -u insta-messaging --since \"$HOURS hours ago\" --no-pager"
else
    echo "Note: Run this script on the test server (185.156.43.172)"
    echo "Usage: ssh root@185.156.43.172 'bash -s' < scripts/check-errors.sh"
    exit 1
fi

echo -e "${YELLOW}📊 Service Status${NC}"
echo "======================================"
systemctl status insta-messaging --no-pager | head -10
echo ""

echo -e "${YELLOW}🔥 Critical Errors${NC}"
echo "======================================"
CRITICAL_COUNT=$(eval $LOG_CMD | grep -c "CRITICAL" || echo "0")
if [ "$CRITICAL_COUNT" -gt 0 ]; then
    echo -e "${RED}Found $CRITICAL_COUNT critical errors:${NC}"
    eval $LOG_CMD | grep "CRITICAL" | tail -10
else
    echo -e "${GREEN}No critical errors found${NC}"
fi
echo ""

echo -e "${YELLOW}❌ Errors${NC}"
echo "======================================"
ERROR_COUNT=$(eval $LOG_CMD | grep -c "ERROR" || echo "0")
if [ "$ERROR_COUNT" -gt 0 ]; then
    echo -e "${RED}Found $ERROR_COUNT errors:${NC}"
    eval $LOG_CMD | grep "ERROR" | tail -20
else
    echo -e "${GREEN}No errors found${NC}"
fi
echo ""

echo -e "${YELLOW}⚠️  Warnings${NC}"
echo "======================================"
WARNING_COUNT=$(eval $LOG_CMD | grep -c "WARNING" || echo "0")
if [ "$WARNING_COUNT" -gt 0 ]; then
    echo -e "${YELLOW}Found $WARNING_COUNT warnings:${NC}"
    eval $LOG_CMD | grep "WARNING" | tail -10
else
    echo -e "${GREEN}No warnings found${NC}"
fi
echo ""

echo -e "${YELLOW}💥 Exceptions/Tracebacks${NC}"
echo "======================================"
EXCEPTION_COUNT=$(eval $LOG_CMD | grep -cE "(Exception|Traceback)" || echo "0")
if [ "$EXCEPTION_COUNT" -gt 0 ]; then
    echo -e "${RED}Found $EXCEPTION_COUNT exceptions:${NC}"
    eval $LOG_CMD | grep -E "(Exception|Traceback)" -A 10 | tail -30
else
    echo -e "${GREEN}No exceptions found${NC}"
fi
echo ""

echo -e "${YELLOW}🔄 Service Restarts${NC}"
echo "======================================"
RESTART_COUNT=$(eval $LOG_CMD | grep -c "Starting Instagram Messenger" || echo "0")
echo "Service has restarted $RESTART_COUNT times in the last $HOURS hours"
if [ "$RESTART_COUNT" -gt 5 ]; then
    echo -e "${RED}⚠️  High restart count - service may be crashing${NC}"
fi
echo ""

echo -e "${YELLOW}📈 Summary${NC}"
echo "======================================"
echo "Time Period: Last $HOURS hours"
echo "Critical Errors: $CRITICAL_COUNT"
echo "Errors: $ERROR_COUNT"
echo "Warnings: $WARNING_COUNT"
echo "Exceptions: $EXCEPTION_COUNT"
echo "Service Restarts: $RESTART_COUNT"
echo ""

if [ "$ERROR_COUNT" -eq 0 ] && [ "$CRITICAL_COUNT" -eq 0 ] && [ "$EXCEPTION_COUNT" -eq 0 ]; then
    echo -e "${GREEN}✅ No critical issues found!${NC}"
else
    echo -e "${RED}⚠️  Issues found - review errors above${NC}"
fi
echo ""

echo "======================================"
echo "💡 Helpful Commands:"
echo "======================================"
echo "View all logs:        journalctl -u insta-messaging -f"
echo "Restart service:      systemctl restart insta-messaging"
echo "Check migrations:     cd /opt/insta-messaging && sudo -u insta-messaging venv/bin/alembic current"
echo "Test health endpoint: curl http://localhost:8000/health"
echo ""
