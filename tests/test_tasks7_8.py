"""
Test script for Tasks 7 & 8: Message status and health endpoints

Tests:
- GET /api/v1/messages/{message_id}/status
- GET /health
"""
import httpx
import asyncio
import json


async def test_health_endpoint():
    """Test the health endpoint"""
    base_url = "http://localhost:8000"
    
    print("\n" + "="*60)
    print("Testing GET /health")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{base_url}/health", timeout=5.0)
            
            print(f"📊 Status Code: {response.status_code}")
            print(f"📄 Response: {json.dumps(response.json(), indent=2)}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy" and "timestamp" in data:
                    print("\n✅ Health endpoint working correctly!")
                else:
                    print("\n⚠️  Health endpoint returned unexpected format")
            else:
                print(f"\n❌ Unexpected status code: {response.status_code}")
                
        except httpx.ConnectError:
            print("\n❌ Could not connect to server. Is it running on http://localhost:8000?")
        except Exception as e:
            print(f"\n❌ Error: {e}")


async def test_message_status_endpoint():
    """Test the message status endpoint"""
    base_url = "http://localhost:8000"
    
    print("\n" + "="*60)
    print("Testing GET /api/v1/messages/{message_id}/status")
    print("="*60)
    
    headers = {
        "Authorization": "Bearer test_key"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            # Test 1: Query non-existent message (should return 404)
            print("\n📝 Test 1: Query non-existent message")
            response = await client.get(
                f"{base_url}/api/v1/messages/nonexistent_id/status",
                headers=headers,
                timeout=5.0
            )
            
            print(f"📊 Status Code: {response.status_code}")
            print(f"📄 Response: {json.dumps(response.json(), indent=2)}")
            
            if response.status_code == 404:
                print("✅ Correctly returns 404 for non-existent message")
            else:
                print(f"❌ Expected 404, got {response.status_code}")
            
            # Test 2: Create a message first, then query its status
            print("\n📝 Test 2: Create message and query status")
            
            # Create a message
            create_payload = {
                "account_id": "test_account_1",
                "recipient_id": "1558635688632972",
                "message": "Test message for status query",
                "idempotency_key": f"test_status_{asyncio.get_event_loop().time()}"
            }
            
            create_response = await client.post(
                f"{base_url}/api/v1/messages/send",
                json=create_payload,
                headers=headers,
                timeout=10.0
            )
            
            if create_response.status_code == 202:
                message_data = create_response.json()
                message_id = message_data.get("message_id")
                print(f"✅ Message created: {message_id}")
                
                # Query the status
                status_response = await client.get(
                    f"{base_url}/api/v1/messages/{message_id}/status",
                    headers=headers,
                    timeout=5.0
                )
                
                print(f"\n📊 Status Query Response:")
                print(f"Status Code: {status_response.status_code}")
                print(f"Response: {json.dumps(status_response.json(), indent=2)}")
                
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    if status_data.get("message_id") == message_id:
                        print("\n✅ Status endpoint working correctly!")
                        print(f"   Message Status: {status_data.get('status')}")
                    else:
                        print("\n⚠️  Message ID mismatch in response")
                else:
                    print(f"\n❌ Expected 200, got {status_response.status_code}")
            else:
                print(f"❌ Failed to create message: {create_response.status_code}")
                
        except httpx.ConnectError:
            print("\n❌ Could not connect to server. Is it running on http://localhost:8000?")
        except Exception as e:
            print(f"\n❌ Error: {e}")


async def main():
    """Run all tests"""
    print("=" * 60)
    print("Tasks 7 & 8: Message Status and Health Endpoints Test")
    print("=" * 60)
    print("\nMake sure:")
    print("1. Server is running (python -m uvicorn app.main:app --reload)")
    print("2. Database is migrated (alembic upgrade head)")
    
    await test_health_endpoint()
    await test_message_status_endpoint()
    
    print("\n" + "=" * 60)
    print("Tests Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
