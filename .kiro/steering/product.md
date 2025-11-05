# Product Overview

Instagram Messenger Automation is an automated DM response system for e-commerce businesses. The system receives customer messages via Instagram Direct Messages through Facebook's webhook callbacks and automatically responds based on predefined rules.

## Current Status

**Phase 1 (MVP)**: Basic webhook and messaging functionality - Complete ✅
**Phase 2 (In Progress)**: Architecture refactoring for multi-account support 🔄

The MVP supports single Instagram business account messaging. The current refactoring focuses on:
- Multi-account architecture with MySQL database
- Interface-driven design (IMessageReceiver, IMessageSender)
- Encrypted credential storage per account
- Account-specific routing and configuration

## Key Features

- Webhook integration with Facebook/Instagram Graph API
- Inbound message processing and storage
- Outbound message sending capability
- Database persistence for messages and conversations
- Multi-tenant support (target architecture)

## Development Environment

- Local development on Windows with ngrok for webhook tunneling
- Deployment targets: Railway or custom Linux server
