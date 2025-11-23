# Requirements Document

## Introduction

This feature adds dual storage capability to the Instagram messenger automation system. Messages will be stored in both the local SQLite database (for UI and reading) and the external CRM MySQL database (for CRM system integration). This provides a one-way sync from the automation system to the CRM database, ensuring the CRM has a complete message history while maintaining local data for the application's UI.

## Glossary

- **Local Database**: The SQLite database used by the Instagram automation system for storing messages, accounts, and application data
- **CRM Database**: The external MySQL database owned by the CRM system, specifically the `messages` table
- **Dual Storage**: Writing message data to both local and CRM databases simultaneously
- **One-Way Sync**: Data flows from automation system to CRM database only; no reading from CRM database
- **Message Repository**: The data access layer responsible for storing and retrieving messages
- **Instagram Automation System**: The FastAPI application that receives Instagram webhooks and manages message routing

## Requirements

### Requirement 1

**User Story:** As a CRM system, I want to receive all Instagram messages in my MySQL database, so that I can display conversation history in my CRM interface.

#### Acceptance Criteria

1. WHEN an inbound Instagram message is received THEN the system SHALL store the message in both local SQLite and CRM MySQL databases
2. WHEN an outbound message is sent via the API THEN the system SHALL store the message in both local SQLite and CRM MySQL databases
3. WHEN storing to CRM MySQL THEN the system SHALL map local message fields to CRM table schema (user_id, username, direction, message, created_at)
4. WHEN the CRM MySQL connection fails THEN the system SHALL log the error and continue operation with local storage only
5. WHEN storing to CRM MySQL THEN the system SHALL use the credentials configured in environment variables

### Requirement 2

**User Story:** As a system administrator, I want CRM database failures to not break the application, so that Instagram message processing continues even if the CRM is unavailable.

#### Acceptance Criteria

1. WHEN CRM MySQL storage fails THEN the system SHALL log the error with full details
2. WHEN CRM MySQL storage fails THEN the system SHALL NOT raise exceptions that stop message processing
3. WHEN CRM MySQL storage fails THEN the system SHALL successfully complete local storage
4. WHEN CRM MySQL connection is unavailable THEN the system SHALL continue processing messages using local storage only
5. WHEN CRM MySQL storage fails THEN the system SHALL include a TODO reminder in logs about missing fields in CRM schema

### Requirement 3

**User Story:** As a developer, I want clear configuration for CRM database connection, so that I can easily enable or disable CRM sync in different environments.

#### Acceptance Criteria

1. WHEN the application starts THEN the system SHALL load CRM MySQL credentials from environment variables
2. WHEN CRM_MYSQL_ENABLED is false THEN the system SHALL skip CRM storage entirely
3. WHEN CRM_MYSQL_ENABLED is true and credentials are missing THEN the system SHALL log a warning and disable CRM sync
4. WHEN CRM database credentials are configured THEN the system SHALL validate the connection on startup
5. WHEN connection validation fails THEN the system SHALL log the error and continue with local storage only

### Requirement 4

**User Story:** As a developer, I want to map Instagram message data to the CRM schema, so that messages are stored correctly despite schema differences.

#### Acceptance Criteria

1. WHEN mapping message data THEN the system SHALL set user_id to the Instagram sender PSID
2. WHEN mapping message data THEN the system SHALL set username to the Instagram username if available
3. WHEN mapping message data THEN the system SHALL set direction to 'in' for inbound messages and 'out' for outbound messages
4. WHEN mapping message data THEN the system SHALL set message to the message text content
5. WHEN mapping message data THEN the system SHALL set created_at to the message timestamp
6. WHEN username is not available THEN the system SHALL use user_id as the username value

### Requirement 5

**User Story:** As a system maintainer, I want connection pooling for CRM MySQL, so that database connections are managed efficiently.

#### Acceptance Criteria

1. WHEN the application starts THEN the system SHALL create a connection pool for CRM MySQL with minimum 1 and maximum 5 connections
2. WHEN storing messages THEN the system SHALL reuse connections from the pool
3. WHEN the application shuts down THEN the system SHALL close all CRM MySQL connections gracefully
4. WHEN a connection is idle for more than 3600 seconds THEN the system SHALL recycle the connection
5. WHEN the connection pool is exhausted THEN the system SHALL wait up to 30 seconds for an available connection before failing

### Requirement 6

**User Story:** As a developer, I want the CRM sync to be non-blocking, so that slow CRM database writes don't impact Instagram webhook response times.

#### Acceptance Criteria

1. WHEN storing a message THEN the system SHALL write to local SQLite first
2. WHEN local storage succeeds THEN the system SHALL write to CRM MySQL asynchronously
3. WHEN CRM MySQL write is in progress THEN the system SHALL NOT block the webhook response
4. WHEN CRM MySQL write completes THEN the system SHALL log success or failure
5. WHEN CRM MySQL write takes longer than 5 seconds THEN the system SHALL log a performance warning
