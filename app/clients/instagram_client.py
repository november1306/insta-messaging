"""
Instagram Graph API client for sending messages.

MVP: Uses global access token from settings (single account).
Phase 6: Will support multiple accounts with account-specific tokens.
"""
import httpx
import logging
from dataclasses import dataclass
from typing import Optional
from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class SendMessageResponse:
    """Response from Instagram Send API"""
    message_id: str
    recipient_id: str
    success: bool
    error_message: Optional[str] = None


class InstagramAPIError(Exception):
    """Exception raised when Instagram API request fails"""
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[dict] = None):
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(self.message)


class InstagramClient:
    """
    Client for Instagram Graph API.
    
    Handles sending messages to Instagram users via the Instagram Graph API.
    
    MVP: Uses global access token from settings (single account).
    TODO (Phase 6): Accept account_id parameter and fetch account-specific token from database.
    """
    
    def __init__(
        self, 
        http_client: httpx.AsyncClient,
        settings: Settings,
        logger_instance: logging.Logger = logger
    ):
        """
        Initialize Instagram API client.
        
        Args:
            http_client: httpx AsyncClient for making HTTP requests
            settings: Application settings containing access token
            logger_instance: Logger for tracking API calls
        """
        self._http_client = http_client
        self._settings = settings
        self._logger = logger_instance
        self._api_base_url = "https://graph.instagram.com/v21.0"
    
    async def send_message(
        self, 
        recipient_id: str, 
        message_text: str
    ) -> SendMessageResponse:
        """
        Send a text message to an Instagram user.
        
        Args:
            recipient_id: Instagram user's PSID (Page-Scoped ID)
            message_text: The text message to send
            
        Returns:
            SendMessageResponse with message_id and status
            
        Raises:
            InstagramAPIError: If the API request fails
            
        Example:
            response = await client.send_message(
                recipient_id="1558635688632972",
                message_text="Thanks for your message!"
            )
        """
        url = f"{self._api_base_url}/me/messages"
        
        # Prepare request payload
        payload = {
            "recipient": {
                "id": recipient_id
            },
            "message": {
                "text": message_text
            },
            "access_token": self._settings.instagram_page_access_token
        }
        
        self._logger.info(f"Sending message to recipient {recipient_id}")
        
        try:
            # Make API request
            response = await self._http_client.post(
                url,
                json=payload,
                timeout=10.0
            )
            
            # Check for successful response
            if response.status_code == 200:
                response_data = response.json()
                message_id = response_data.get("message_id")
                recipient_id_response = response_data.get("recipient_id")
                
                self._logger.info(
                    f"✅ Message sent successfully - "
                    f"message_id: {message_id}, recipient: {recipient_id_response}"
                )
                
                return SendMessageResponse(
                    message_id=message_id,
                    recipient_id=recipient_id_response,
                    success=True
                )
            else:
                # API returned error
                error_data = response.json() if response.text else {}
                error_message = error_data.get("error", {}).get("message", "Unknown error")
                error_code = error_data.get("error", {}).get("code")
                
                self._logger.error(
                    f"❌ Instagram API error - "
                    f"status: {response.status_code}, "
                    f"code: {error_code}, "
                    f"message: {error_message}, "
                    f"recipient: {recipient_id}"
                )
                
                raise InstagramAPIError(
                    message=f"Instagram API error: {error_message}",
                    status_code=response.status_code,
                    response_body=error_data
                )
                
        except httpx.TimeoutException as e:
            self._logger.error(f"❌ Request timeout sending message to {recipient_id}: {e}")
            raise InstagramAPIError(
                message=f"Request timeout: {str(e)}",
                status_code=None,
                response_body=None
            ) from e
            
        except httpx.RequestError as e:
            self._logger.error(f"❌ Request error sending message to {recipient_id}: {e}")
            raise InstagramAPIError(
                message=f"Request error: {str(e)}",
                status_code=None,
                response_body=None
            ) from e
            
        except Exception as e:
            self._logger.error(f"❌ Unexpected error sending message to {recipient_id}: {e}", exc_info=True)
            raise InstagramAPIError(
                message=f"Unexpected error: {str(e)}",
                status_code=None,
                response_body=None
            ) from e
