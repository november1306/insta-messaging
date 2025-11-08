"""Quick test for task 4 after fixes"""
import requests
import json

url = "http://localhost:8000/api/v1/accounts"
headers = {
    "Authorization": "Bearer test_key",
    "Content-Type": "application/json"
}

# Use a different account ID to avoid duplicate error
payload = {
    "instagram_account_id": "17841400000000999",
    "username": "testshop_fixed",
    "access_token": "test_token_fixed",
    "crm_webhook_url": "https://crm.example.com/webhooks/instagram",
    "webhook_secret": "webhook_secret_fixed"
}

print("Testing fixed endpoint...")
response = requests.post(url, headers=headers, json=payload)
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")

if response.status_code == 201:
    print("\n✅ Task 4 working correctly after fixes!")
else:
    print("\n❌ Something went wrong")
