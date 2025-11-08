"""
Test script for Task 6: Instagram delivery integration

Tests the POST /api/v1/messages/send endpoint with actual Instagram delivery.
"""
import httpx
import asyncio
import json


async def test_send_message():
    """Test sending a message via the CRM API"""
    
    base_url = "http://localhost:8000"
    
    # Test data
    payload = {
        "account_id": "test_account_1",
        "recipient_id": "1558635688632972",  # Replace with actual Instagram PSID
        "message": "Test message from CRM API (Task 6)",
        "idempotency_key": f"test_task6_{asyncio.get_event_loop().time()}"
    }
    
    headers = {
        "Authorization": "Bearer test_key",
        "Content-Type": "application/json"
    }
    
    print("🧪 Testing POST /api/v1/messages/send with Instagram delivery...")
    print(f"📤 Payload: {json.dumps(payload, indent=2)}")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{base_url}/api/v1/messages/send",
                json=payload,
                headers=headers,
                timeout=30.0
            )
            
            print(f"\n📊 Response Status: {response.status_code}")
            print(f"📄 Response Body: {json.dumps(response.json(), indent=2)}")
            
            if response.status_code == 202:
                print("\n✅ Message accepted!")
                
                # Check the status
                response_data = response.json()
                if response_data.get("status") == "sent":
                    print("✅ Message successfully sent to Instagram!")
                elif response_data.get("status") == "failed":
                    print("❌ Message delivery failed")
                else:
                    print(f"⏳ Message status: {response_data.get('status')}")
            else:
                print(f"\n❌ Unexpected status code: {response.status_code}")
                
        except httpx.ConnectError:
            print("\n❌ Could not connect to server. Is it running on http://localhost:8000?")
        except Exception as e:
            print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("Task 6: Instagram Delivery Test")
    print("=" * 60)
    print("\nMake sure:")
    print("1. Server is running (python -m uvicorn app.main:app --reload)")
    print("2. INSTAGRAM_PAGE_ACCESS_TOKEN is set in .env")
    print("3. Replace recipient_id with a valid Instagram PSID\n")
    
    asyncio.run(test_send_message())
