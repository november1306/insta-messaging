"""
Test script for accounts API endpoint
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_create_account():
    """Test POST /api/v1/accounts"""
    url = f"{BASE_URL}/api/v1/accounts"
    
    headers = {
        "Authorization": "Bearer test_key",
        "Content-Type": "application/json"
    }
    
    payload = {
        "instagram_account_id": "17841400000000001",
        "username": "testshop",
        "access_token": "test_token_123",
        "crm_webhook_url": "https://crm.example.com/webhooks/instagram",
        "webhook_secret": "webhook_secret_xyz"
    }
    
    print("Testing POST /api/v1/accounts...")
    print(f"Request: {json.dumps(payload, indent=2)}")
    
    response = requests.post(url, headers=headers, json=payload)
    
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 201:
        print("\n✅ Account created successfully!")
        return response.json()
    else:
        print("\n❌ Failed to create account")
        return None


def test_create_duplicate():
    """Test creating duplicate account (should fail)"""
    url = f"{BASE_URL}/api/v1/accounts"
    
    headers = {
        "Authorization": "Bearer test_key",
        "Content-Type": "application/json"
    }
    
    payload = {
        "instagram_account_id": "17841400000000001",  # Same as above
        "username": "testshop2",
        "access_token": "test_token_456",
        "crm_webhook_url": "https://crm.example.com/webhooks/instagram",
        "webhook_secret": "webhook_secret_abc"
    }
    
    print("\n\nTesting duplicate account creation...")
    response = requests.post(url, headers=headers, json=payload)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 400:
        print("\n✅ Duplicate correctly rejected!")
    else:
        print("\n❌ Expected 400 error for duplicate")


def test_missing_auth():
    """Test without Authorization header (should fail)"""
    url = f"{BASE_URL}/api/v1/accounts"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    payload = {
        "instagram_account_id": "17841400000000002",
        "username": "testshop3",
        "access_token": "test_token_789",
        "crm_webhook_url": "https://crm.example.com/webhooks/instagram",
        "webhook_secret": "webhook_secret_def"
    }
    
    print("\n\nTesting missing Authorization header...")
    response = requests.post(url, headers=headers, json=payload)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 401:
        print("\n✅ Unauthorized correctly rejected!")
    else:
        print("\n❌ Expected 401 error for missing auth")


if __name__ == "__main__":
    # Test 1: Create account
    account = test_create_account()
    
    # Test 2: Try to create duplicate
    test_create_duplicate()
    
    # Test 3: Missing auth
    test_missing_auth()
