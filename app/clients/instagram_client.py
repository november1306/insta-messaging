"""
Instagram Graph API client for sending messages.

Uses per-account OAuth tokens for multi-account support.
"""
import httpx
import logging
from dataclasses import dataclass
from typing import Optional

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
    Uses per-account OAuth access tokens from the database.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        access_token: str,
        logger_instance: logging.Logger = logger
    ):
        """
        Initialize Instagram API client with per-account OAuth token.

        Args:
            http_client: httpx AsyncClient for making HTTP requests
            access_token: Per-account Instagram access token (required)
            logger_instance: Logger for tracking API calls

        Raises:
            ValueError: If access_token is empty or None
        """
        if not access_token:
            raise ValueError(
                "access_token is required. OAuth accounts must provide a valid access token."
            )

        self._http_client = http_client
        self._logger = logger_instance
        self._api_base_url = "https://graph.instagram.com/v21.0"
        self._token = access_token

        self._logger.debug("InstagramClient initialized with per-account OAuth token")
    
    async def get_user_profile(self, user_id: str) -> Optional[dict]:
        """
        Get user profile information from Instagram.

        NOTE: Instagram-Scoped IDs (sender IDs) support 'name', 'username', and 'profile_pic' fields.
        Requires User Profile API permission (pages_messaging) to retrieve profile_pic.

        Args:
            user_id: Instagram user's PSID (Page-Scoped ID / Instagram-Scoped ID)

        Returns:
            Dictionary with user profile data (name, username, profile_pic) or None if failed
            Note: Field is 'profile_pic' for ISGIDs, not 'profile_picture_url'

        Example:
            profile = await client.get_user_profile("1558635688632972")
            # Returns: {"name": "John Doe", "username": "johndoe", "profile_pic": "https://..."}
        """
        url = f"{self._api_base_url}/{user_id}"

        try:
            response = await self._http_client.get(
                url,
                params={
                    # IMPORTANT: Use 'profile_pic' for Instagram-Scoped IDs (customers)
                    # Use 'profile_picture_url' only for business accounts via get_business_account_profile()
                    # Requires User Profile API permission (pages_messaging)
                    "fields": "name,username,profile_pic",  # Note: profile_pic for IGSID, not profile_picture_url
                    "access_token": self._token
                },
                timeout=5.0
            )
            
            if response.status_code == 200:
                profile_data = response.json()
                self._logger.info(f"✅ Retrieved profile for user {user_id}")
                return profile_data
            else:
                error_data = response.json() if response.text else {}
                error_message = error_data.get("error", {}).get("message", "Unknown error")
                self._logger.warning(
                    f"⚠️ Failed to get user profile - status: {response.status_code}, "
                    f"message: {error_message}"
                )
                return None
                
        except Exception as e:
            self._logger.warning(f"⚠️ Error fetching user profile for {user_id}: {e}")
            return None

    async def get_business_account_profile(self, ig_user_id: str) -> Optional[dict]:
        """
        Get business account profile information from Instagram Graph API.

        For Instagram Business/Creator accounts (IG User ID), use different fields
        than regular user profiles.

        Args:
            ig_user_id: Instagram Business Account ID (IG User ID)

        Returns:
            Dictionary with business profile data or None if failed
            {
                "username": "business_name",
                "profile_picture_url": "https://...",
                "biography": "Bio text",
                "followers_count": 1234
            }
        """
        url = f"{self._api_base_url}/{ig_user_id}"

        try:
            response = await self._http_client.get(
                url,
                params={
                    "fields": "username,profile_picture_url,biography,followers_count",
                    "access_token": self._token
                },
                timeout=5.0
            )

            if response.status_code == 200:
                profile_data = response.json()
                self._logger.info(f"✅ Retrieved business profile for {ig_user_id}: @{profile_data.get('username')}")
                return profile_data
            else:
                error_data = response.json() if response.text else {}
                error_message = error_data.get("error", {}).get("message", "Unknown error")
                self._logger.warning(
                    f"⚠️ Failed to get business profile - status: {response.status_code}, "
                    f"message: {error_message}"
                )
                return None

        except Exception as e:
            self._logger.warning(f"⚠️ Error fetching business profile for {ig_user_id}: {e}")
            return None

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
            ValueError: If recipient_id or message_text is invalid
            InstagramAPIError: If the API request fails
            
        Example:
            response = await client.send_message(
                recipient_id="1558635688632972",
                message_text="Thanks for your message!"
            )
        """
        # Input validation
        if not recipient_id or not recipient_id.strip():
            raise ValueError("recipient_id cannot be empty")
        
        if not message_text or not message_text.strip():
            raise ValueError("message_text cannot be empty")
        
        # Instagram has a 1000 character limit for text messages
        if len(message_text) > 1000:
            raise ValueError(
                f"message_text exceeds 1000 character limit (got {len(message_text)} characters)"
            )
        
        url = f"{self._api_base_url}/me/messages"
        
        # Prepare request payload (access token sent as URL parameter per Instagram best practices)
        payload = {
            "recipient": {
                "id": recipient_id
            },
            "message": {
                "text": message_text
            }
        }
        
        self._logger.info(f"Sending message to recipient {recipient_id}")
        
        try:
            # Make API request (access token as URL parameter per Instagram best practices)
            response = await self._http_client.post(
                url,
                params={"access_token": self._token},
                json=payload,
                timeout=10.0
            )
            
            # Check for successful response
            if response.status_code == 200:
                response_data = response.json()
                message_id = response_data.get("message_id")
                recipient_id_response = response_data.get("recipient_id")
                
                # Validate required fields in response
                if not message_id or not recipient_id_response:
                    raise InstagramAPIError(
                        "Invalid API response: missing message_id or recipient_id",
                        status_code=200,
                        response_body=response_data
                    )
                
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

    async def send_message_with_attachment(
        self,
        recipient_id: str,
        attachment_url: str,
        attachment_type: str,
        caption_text: Optional[str] = None
    ) -> SendMessageResponse:
        """
        Send a message with media attachment to an Instagram user.

        Args:
            recipient_id: Instagram user's PSID (Page-Scoped ID)
            attachment_url: Publicly accessible URL to the media file
            attachment_type: Type of attachment ("image", "video", or "audio")
            caption_text: Optional caption text (sent as separate message after attachment)

        Returns:
            SendMessageResponse with message_id and status

        Raises:
            ValueError: If inputs are invalid
            InstagramAPIError: If the API request fails

        Example:
            response = await client.send_message_with_attachment(
                recipient_id="1558635688632972",
                attachment_url="https://example.com/media/image.jpg",
                attachment_type="image",
                caption_text="Check this out!"
            )
        """
        # Input validation
        if not recipient_id or not recipient_id.strip():
            raise ValueError("recipient_id cannot be empty")

        if not attachment_url or not attachment_url.strip():
            raise ValueError("attachment_url cannot be empty")

        if attachment_type not in ["image", "video", "audio"]:
            raise ValueError(f"attachment_type must be 'image', 'video', or 'audio', got: {attachment_type}")

        url = f"{self._api_base_url}/me/messages"

        # Prepare request payload
        payload = {
            "recipient": {
                "id": recipient_id
            },
            "message": {
                "attachment": {
                    "type": attachment_type,
                    "payload": {
                        "url": attachment_url,
                        "is_reusable": False
                    }
                }
            }
        }

        self._logger.info(
            f"Sending {attachment_type} attachment to recipient {recipient_id}, URL: {attachment_url}"
        )

        try:
            # Make API request
            response = await self._http_client.post(
                url,
                params={"access_token": self._token},
                json=payload,
                timeout=30.0  # Longer timeout for media uploads
            )

            # Check for successful response
            if response.status_code == 200:
                response_data = response.json()
                message_id = response_data.get("message_id")
                recipient_id_response = response_data.get("recipient_id")

                # Validate required fields in response
                if not message_id or not recipient_id_response:
                    raise InstagramAPIError(
                        "Invalid API response: missing message_id or recipient_id",
                        status_code=200,
                        response_body=response_data
                    )

                self._logger.info(
                    f"✅ {attachment_type.capitalize()} attachment sent successfully - "
                    f"message_id: {message_id}, recipient: {recipient_id_response}"
                )

                # If caption provided, send as separate text message
                if caption_text and caption_text.strip():
                    self._logger.info(f"Sending caption as separate message...")
                    try:
                        await self.send_message(recipient_id, caption_text.strip())
                    except Exception as e:
                        # Log caption failure but don't fail the whole request
                        self._logger.warning(
                            f"⚠️  Attachment sent but caption failed: {e}"
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
                    f"❌ Instagram API error sending attachment - "
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
            self._logger.error(f"❌ Request timeout sending attachment to {recipient_id}: {e}")
            raise InstagramAPIError(
                message=f"Request timeout: {str(e)}",
                status_code=None,
                response_body=None
            ) from e

        except httpx.RequestError as e:
            self._logger.error(f"❌ Request error sending attachment to {recipient_id}: {e}")
            raise InstagramAPIError(
                message=f"Request error: {str(e)}",
                status_code=None,
                response_body=None
            ) from e

        except Exception as e:
            self._logger.error(f"❌ Unexpected error sending attachment to {recipient_id}: {e}", exc_info=True)
            raise InstagramAPIError(
                message=f"Unexpected error: {str(e)}",
                status_code=None,
                response_body=None
            ) from e

    async def get_conversations(
        self,
        limit: int = 50,
        include_messages: bool = True
    ) -> Optional[list[dict]]:
        """
        Fetch conversations from Instagram Messaging API.

        Endpoint: GET /v21.0/me/conversations

        Args:
            limit: Maximum number of conversations to fetch (default 50)
            include_messages: Whether to include nested message data (default True)
                            False = faster, only gets conversation metadata (~4s)
                            True = slower, includes full message history (~15s for 50 conversations)

        Returns:
            List of conversation objects with:
            - id: Conversation ID
            - participants: List of participant objects (always included)
            - messages: Preview of latest messages (if include_messages=True)
            - updated_time: Last activity timestamp (always included)

            Returns None if API call fails or endpoint not available.

        Note: This endpoint may not be available for all Instagram accounts.
              The method gracefully degrades by returning None on failure.
        """
        url = f"{self._api_base_url}/me/conversations"

        # Build field list based on whether we want messages
        if include_messages:
            fields = "id,participants,messages{message,from,created_time},updated_time"
            timeout = 30.0  # Longer timeout for full data
        else:
            fields = "id,participants,updated_time"
            timeout = 10.0  # Shorter timeout for minimal data

        try:
            response = await self._http_client.get(
                url,
                params={
                    "fields": fields,
                    "limit": limit,
                    "access_token": self._token
                },
                timeout=timeout
            )

            if response.status_code == 200:
                data = response.json()
                conversations = data.get("data", [])
                self._logger.info(f"✅ Retrieved {len(conversations)} conversations (include_messages={include_messages})")
                return conversations
            else:
                error_data = response.json() if response.text else {}
                error_message = error_data.get("error", {}).get("message", "Unknown error")
                self._logger.warning(
                    f"⚠️ Failed to get conversations - status: {response.status_code}, "
                    f"message: {error_message}"
                )
                return None

        except Exception as e:
            self._logger.warning(f"⚠️ Error fetching conversations: {e}")
            return None

    async def get_conversation_messages(
        self,
        conversation_id: str,
        limit: int = 25
    ) -> Optional[list[dict]]:
        """
        Fetch messages for a specific conversation.

        Endpoint: GET /v21.0/{conversation_id}/messages

        Args:
            conversation_id: Instagram conversation ID
            limit: Max messages to fetch (default 25)

        Returns:
            List of message objects with:
            - id: Message ID
            - message: Message text
            - from: Sender info
            - created_time: Timestamp
            - attachments: Media attachments (if any)

            Returns None if API call fails.

        Note: This method supports graceful degradation by returning None on failure.
        """
        url = f"{self._api_base_url}/{conversation_id}/messages"

        try:
            response = await self._http_client.get(
                url,
                params={
                    "fields": "id,message,from,created_time,attachments",
                    "limit": limit,
                    "access_token": self._token
                },
                timeout=10.0
            )

            if response.status_code == 200:
                data = response.json()
                messages = data.get("data", [])
                self._logger.info(f"✅ Retrieved {len(messages)} messages for conversation {conversation_id}")
                return messages
            else:
                error_data = response.json() if response.text else {}
                error_message = error_data.get("error", {}).get("message", "Unknown error")
                self._logger.warning(
                    f"⚠️ Failed to get messages - status: {response.status_code}, "
                    f"message: {error_message}"
                )
                return None

        except Exception as e:
            self._logger.warning(f"⚠️ Error fetching messages for {conversation_id}: {e}")
            return None
