#!/bin/bash
# Authentication Test Script

echo "=========================================="
echo " JWT Authentication Test"
echo "=========================================="
echo ""

# Test 1: Create Session
echo "[1/4] Creating session..."
curl -s -X POST http://localhost:8000/api/v1/ui/session > /tmp/session.json
TOKEN=$(cat /tmp/session.json | python -c "import sys, json; print(json.load(sys.stdin)['token'])")
ACCOUNT_ID=$(cat /tmp/session.json | python -c "import sys, json; print(json.load(sys.stdin)['account_id'])")
echo "✓ Session created for account: $ACCOUNT_ID"
echo "✓ Token: ${TOKEN:0:50}..."
echo ""

# Test 2: GET /ui/account/me
echo "[2/4] Testing GET /ui/account/me..."
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/ui/account/me | python -m json.tool
echo ""

# Test 3: GET /ui/conversations
echo "[3/4] Testing GET /ui/conversations..."
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/ui/conversations | python -c "import sys, json; data = json.load(sys.stdin); print(f\"✓ Found {len(data['conversations'])} conversations\")"
echo ""

# Test 4: Test without token (should fail with 401)
echo "[4/4] Testing without token (should fail)..."
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" http://localhost:8000/api/v1/ui/account/me)
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
if [ "$HTTP_CODE" = "401" ]; then
    echo "✓ Correctly rejected with 401 Unauthorized"
else
    echo "✗ Expected 401 but got: $HTTP_CODE"
fi

echo ""
echo "=========================================="
echo " ✓ All Tests Complete"
echo "=========================================="
