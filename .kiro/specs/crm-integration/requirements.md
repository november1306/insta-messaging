# Requirements Document

## Introduction

This feature implements a bidirectional integration between the Instagram Messenger Automation service (message router) and a custom e-commerce CRM system. The integration enables the CRM to send messages to customers via Instagram and receive incoming messages for display in a dedicated communication tab (chat window). 

**Core MVP Purpose:** Enable a CRM chat window where customer service representatives can:
1. **See customer messages** in real-time (Instagram → Router → CRM webhook)
2. **Send replies** to customers (CRM → Router API → Instagram)

The architecture follows a webhook-first approach for loose coupling, with clear separation of concerns between the message router (handles Instagram API complexity) and the CRM (handles business logic and customer data).

## Glossary

- **Message Router**: The Instagram Messenger Automation service that handles Instagram API integration
- **CRM System**: Custom e-commerce customer relationship management system
- **Webhook**: HTTP callback that delivers real-time event notifications
- **Idempotency Key**: Unique identifier to prevent duplicate message sends
- **PSID**: Page-Scoped ID - Instagram's unique identifier for a user in context of a business page
- **Delivery Status**: State of a message (pending, sent, delivered, failed, read)
- **Message Event**: Notification of a message-related occurrence (received, delivered, read, failed)

## Requirements

### Requirement 1: Outbound Message API

**User Story:** As a CRM system, I want to send Instagram messages to customers via the message router API, so that customer service representatives can communicate with customers from within the CRM interface.

#### Acceptance Criteria

1. WHEN the CRM sends a POST request to /api/v1/messages/send THEN the Message Router SHALL validate the request payload and authentication
2. IF the request lacks valid authentication credentials THEN the Message Router SHALL return a 401 Unauthorized response
3. WHEN a valid send request is received THEN the Message Router SHALL accept the message and return a 202 Accepted response with a message_id
4. WHEN the Message Router accepts a message THEN the Message Router SHALL attempt delivery via Instagram API within 5 seconds
5. IF the idempotency_key matches a previous request THEN the Message Router SHALL return the existing message_id without sending a duplicate
6. WHEN the Instagram API returns an error THEN the Message Router SHALL retry up to 3 times with exponential backoff
7. IF all retry attempts fail THEN the Message Router SHALL store the failure status and notify the CRM via webhook

### Requirement 2: Inbound Message Webhooks

**User Story:** As a CRM system, I want to receive incoming Instagram messages via webhooks, so that customer service representatives can see and respond to customer inquiries in real-time.

#### Acceptance Criteria

1. WHEN the Message Router receives an Instagram message THEN the Message Router SHALL forward it to the configured CRM webhook endpoint within 2 seconds
2. WHEN sending a webhook to the CRM THEN the Message Router SHALL include a signature header for validation
3. IF the CRM webhook endpoint returns a non-2xx status code THEN the Message Router SHALL retry up to 5 times with exponential backoff
4. WHEN the CRM webhook endpoint is unreachable THEN the Message Router SHALL store the message and continue retrying for up to 24 hours
5. IF webhook delivery fails after 24 hours THEN the Message Router SHALL move the message to a dead letter queue and alert administrators
6. WHEN the Message Router sends a webhook THEN the Message Router SHALL include all message metadata (sender_id, timestamp, message_type)
7. WHEN multiple messages arrive simultaneously THEN the Message Router SHALL deliver webhooks in chronological order

### Requirement 3: Delivery Status Webhooks

**User Story:** As a CRM system, I want to receive delivery status updates for sent messages, so that customer service representatives can see when messages are delivered and read.

#### Acceptance Criteria

1. WHEN a message delivery status changes THEN the Message Router SHALL send a status webhook to the CRM
2. WHEN sending a status webhook THEN the Message Router SHALL include the original message_id from the send request
3. IF the Instagram API reports message delivered THEN the Message Router SHALL send a "message.delivered" event to the CRM
4. IF the Instagram API reports message read THEN the Message Router SHALL send a "message.read" event to the CRM
5. IF message sending fails permanently THEN the Message Router SHALL send a "message.failed" event with error details
6. WHEN the CRM webhook endpoint is unavailable THEN the Message Router SHALL queue status updates and retry delivery
7. WHEN sending status webhooks THEN the Message Router SHALL include timestamps for each status change

### Requirement 4: Message Status Query API

**User Story:** As a CRM system, I want to query the delivery status of sent messages, so that I can display accurate message status when webhook delivery is delayed or failed.

#### Acceptance Criteria

1. WHEN the CRM sends a GET request to /api/v1/messages/{message_id}/status THEN the Message Router SHALL return the current delivery status
2. IF the message_id does not exist THEN the Message Router SHALL return a 404 Not Found response
3. WHEN returning message status THEN the Message Router SHALL include all status transitions with timestamps
4. WHEN returning message status THEN the Message Router SHALL include any error messages from failed delivery attempts
5. IF the message is still pending THEN the Message Router SHALL return status "pending" with retry attempt count
6. WHEN the CRM queries status THEN the Message Router SHALL respond within 200 milliseconds
7. WHEN returning message status THEN the Message Router SHALL include the Instagram message_id if available

### Requirement 5: Account Configuration API

**User Story:** As a CRM administrator, I want to configure Instagram account settings and webhook endpoints, so that the integration can be set up and managed without code changes.

#### Acceptance Criteria

1. WHEN the CRM sends a POST request to /api/v1/accounts THEN the Message Router SHALL create a new Instagram account configuration
2. WHEN creating an account THEN the Message Router SHALL encrypt and store the Instagram access token
3. WHEN creating an account THEN the Message Router SHALL validate the access token with Instagram API
4. IF the access token is invalid THEN the Message Router SHALL return a 400 Bad Request with error details
5. WHEN the CRM sends a PUT request to /api/v1/accounts/{account_id} THEN the Message Router SHALL update the account configuration
6. WHEN updating an account THEN the Message Router SHALL allow changing the CRM webhook URL
7. WHEN the CRM sends a GET request to /api/v1/accounts/{account_id} THEN the Message Router SHALL return account details without exposing the access token

### Requirement 6: Webhook Signature Validation

**User Story:** As a CRM system, I want to validate webhook signatures, so that I can ensure webhooks are genuinely from the message router and not from malicious sources.

#### Acceptance Criteria

1. WHEN the Message Router sends a webhook to the CRM THEN the Message Router SHALL include an X-Hub-Signature-256 header
2. WHEN generating the signature THEN the Message Router SHALL use HMAC-SHA256 with a shared secret
3. WHEN the CRM validates the signature THEN the CRM SHALL use constant-time comparison to prevent timing attacks
4. IF the signature validation fails THEN the CRM SHALL reject the webhook and return a 401 Unauthorized response
5. WHEN the Message Router receives a 401 response THEN the Message Router SHALL not retry delivery and SHALL alert administrators
6. WHEN configuring an account THEN the Message Router SHALL allow setting a unique webhook secret per account
7. WHEN the webhook secret is rotated THEN the Message Router SHALL use the new secret for all subsequent webhooks

### Requirement 7: Data Storage Separation

**User Story:** As a system architect, I want clear separation between message router data and CRM data, so that each system can evolve independently and maintain its own domain.

#### Acceptance Criteria

1. WHEN the Message Router stores message data THEN the Message Router SHALL store only delivery metadata and Instagram-specific data
2. WHEN the CRM stores message data THEN the CRM SHALL store customer context and business-related data
3. WHEN the Message Router stores a message THEN the Message Router SHALL include message_id, delivery_status, retry_count, and timestamps
4. WHEN the CRM stores a message THEN the CRM SHALL include customer_id, conversation_id, and business context
5. IF the Message Router database is unavailable THEN the CRM SHALL continue to function with cached data
6. IF the CRM database is unavailable THEN the Message Router SHALL continue accepting and delivering messages
7. WHEN either system queries the other THEN the system SHALL use the API rather than direct database access

### Requirement 8: Error Handling and Resilience

**User Story:** As a system administrator, I want robust error handling and retry logic, so that temporary failures do not result in lost messages or broken integrations.

#### Acceptance Criteria

1. WHEN the Instagram API is unavailable THEN the Message Router SHALL queue outbound messages and retry when service is restored
2. WHEN the CRM webhook endpoint is unavailable THEN the Message Router SHALL queue inbound messages and retry delivery
3. WHEN retry attempts are exhausted THEN the Message Router SHALL move failed messages to a dead letter queue
4. WHEN a message is in the dead letter queue THEN the Message Router SHALL expose it via an admin API for manual intervention
5. IF the Message Router restarts THEN the Message Router SHALL resume processing queued messages without data loss
6. WHEN network errors occur THEN the Message Router SHALL distinguish between retryable and non-retryable errors
7. WHEN rate limits are hit THEN the Message Router SHALL respect the retry-after header and queue messages accordingly

### Requirement 9: API Authentication and Authorization

**User Story:** As a security administrator, I want secure authentication between the CRM and message router, so that only authorized systems can send messages and access account data.

#### Acceptance Criteria

1. WHEN the CRM calls the Message Router API THEN the CRM SHALL include an API key in the Authorization header
2. WHEN the Message Router receives an API request THEN the Message Router SHALL validate the API key before processing
3. IF the API key is invalid or missing THEN the Message Router SHALL return a 401 Unauthorized response
4. WHEN an API key is created THEN the Message Router SHALL associate it with specific account permissions
5. IF an API key lacks permission for an account THEN the Message Router SHALL return a 403 Forbidden response
6. WHEN API keys are stored THEN the Message Router SHALL hash them using a secure algorithm
7. WHEN an API key is compromised THEN the Message Router SHALL support immediate revocation without system restart

### Requirement 10: API Documentation and Testing Interface

**User Story:** As a CRM developer, I want interactive API documentation with a testing interface, so that I can understand the API contract and test integration without writing code.

#### Acceptance Criteria

1. WHEN the Message Router starts THEN the Message Router SHALL expose OpenAPI/Swagger documentation at /docs
2. WHEN accessing the documentation THEN the system SHALL display all API endpoints with request/response schemas
3. WHEN viewing an endpoint THEN the documentation SHALL include example requests and responses
4. WHEN using the Swagger UI THEN the developer SHALL be able to execute API calls directly from the browser
5. WHEN testing via Swagger UI THEN the developer SHALL be able to input authentication credentials
6. WHEN the API schema changes THEN the documentation SHALL update automatically without manual editing
7. WHEN viewing webhook payloads THEN the documentation SHALL include webhook event schemas and examples

### Requirement 11: Monitoring and Observability

**User Story:** As a system administrator, I want comprehensive logging and monitoring, so that I can troubleshoot issues and ensure the integration is functioning correctly.

#### Acceptance Criteria

1. WHEN a message is sent or received THEN the Message Router SHALL log the event with message_id and account_id
2. WHEN webhook delivery fails THEN the Message Router SHALL log the failure with HTTP status code and error message
3. WHEN API requests are received THEN the Message Router SHALL log request method, path, and response status
4. IF webhook delivery latency exceeds 5 seconds THEN the Message Router SHALL log a performance warning
5. WHEN the Message Router starts THEN the Message Router SHALL log the configuration status and health check results
6. WHEN logging events THEN the Message Router SHALL never log message content or customer personal data
7. WHEN errors occur THEN the Message Router SHALL include correlation IDs for tracing requests across systems
