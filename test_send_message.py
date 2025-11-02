"""
Test script to send a message from our Instagram business account (@ser_bain) 
to any user using the Instagram Send API

Usage: py test_send_message.py "@username" "message text"
Example: py test_send_message.py "@ser_bain" "Hello from automation!"
"""
import httpx
import asyncio
import sys
from app.config import settings

# User ID mappings (Instagram recipient IDs)
USER_IDS = {
    "@ser_bain": "1180376147344794",      # ser_bain business account
    "@tol1306": "1558635688632972",       # tol1306 personal account
    # Add more users here as needed
}

async def send_test_message(recipient_username: str, message_text: str):
    """Send a test message to specified user"""
    
    # Check if recipient username is valid
    if recipient_username not in USER_IDS:
        print(f"❌ Unknown user: {recipient_username}")
        print(f"Available users: {', '.join(USER_IDS.keys())}")
        return None
    
    recipient_id = USER_IDS[recipient_username]
    
    print(f"📤 Sending message to {recipient_username} (ID: {recipient_id})")
    print(f"💬 Message: {message_text}")
    
    # First, let's test if the token is valid using Instagram Graph API
    test_url = "https://graph.instagram.com/v21.0/me"
    test_headers = {
        "Authorization": f"Bearer {settings.instagram_page_access_token}"
    }
    
    print(f"\n🔍 Testing token validity...")
    
    async with httpx.AsyncClient() as client:
        test_response = await client.get(test_url, headers=test_headers)
        print(f"Token test - Status: {test_response.status_code}")
        
        if test_response.status_code != 200:
            print("❌ Token is invalid or expired")
            return None
        else:
            print("✅ Token is valid")
    
    # Instagram Graph API endpoint
    url = "https://graph.instagram.com/v21.0/me/messages"
    
    # Message payload for Instagram
    payload = {
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "text": message_text
        },
        "messaging_type": "RESPONSE"
    }
    
    # Headers with Bearer token (Instagram Graph API style)
    headers = {
        "Authorization": f"Bearer {settings.instagram_page_access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url, 
                json=payload, 
                headers=headers
            )
            
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")
            
            if response.status_code == 200:
                print("✅ Message sent successfully!")
                return response.json()
            else:
                print("❌ Failed to send message")
                return None
                
    except Exception as e:
        print(f"Error: {e}")
        return None

def main():
    """Main function to handle command line arguments"""
    if len(sys.argv) != 3:
        print("Usage: py test_send_message.py \"@username\" \"message text\"")
        print("Example: py test_send_message.py \"@ser_bain\" \"Hello from automation!\"")
        print(f"Available users: {', '.join(USER_IDS.keys())}")
        sys.exit(1)
    
    recipient_username = sys.argv[1]
    message_text = sys.argv[2]
    
    # Run the async function
    asyncio.run(send_test_message(recipient_username, message_text))

if __name__ == "__main__":
    main()