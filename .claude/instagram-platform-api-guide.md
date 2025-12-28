# Instagram Platform API Guide (July 2024)

**Source**: https://gist.github.com/PrenSJ2/0213e60e834e66b7e09f7f93999163fc

## Overview

Instagram Platform API (Instagram Direct Login) launched in July 2024 allows **direct authentication with Instagram accounts WITHOUT requiring a Facebook Page connection**, supporting both Business and Creator accounts.

## Key Differences: Instagram Business Login vs Facebook Login

### Instagram Business Login (NEW - 2024+)
- ✅ Direct OAuth with Instagram
- ✅ NO Facebook Page required
- ✅ Uses `graph.instagram.com` API
- ✅ Scopes: `instagram_business_basic`, `instagram_business_content_publish`
- ✅ Returns Instagram account ID directly

### Facebook Login (OLD)
- ❌ OAuth via Facebook
- ❌ Requires Facebook Page linked to Instagram
- ❌ Uses `graph.facebook.com/me/accounts` API
- ❌ Scopes: `pages_read_engagement`, `instagram_basic`
- ❌ Must fetch Instagram ID from Page node

## OAuth Flow (Instagram Business Login)

### 1. Authorization URL

```
https://api.instagram.com/oauth/authorize
  ?client_id={app-id}
  &redirect_uri={redirect-uri}
  &scope=instagram_business_basic,instagram_business_content_publish
  &response_type=code
```

**Required Scopes:**
- `instagram_business_basic` - Basic profile access
- `instagram_business_content_publish` - Content publishing

**Optional Scopes:**
- `instagram_business_manage_messages` - For messaging
- `instagram_business_manage_insights` - For analytics
- `instagram_business_manage_comments` - For comment management

### 2. Token Exchange

**Endpoint**: `https://api.instagram.com/oauth/access_token`

**Request:**
```
POST https://api.instagram.com/oauth/access_token
Content-Type: application/x-www-form-urlencoded

client_id={app-id}
&client_secret={app-secret}
&grant_type=authorization_code
&redirect_uri={redirect-uri}
&code={authorization-code}
```

**Response:**
```json
{
  "access_token": "IGQVJ...",
  "user_id": 17841405793187218
}
```

### 3. Get Account Details

**Endpoint**: `https://graph.instagram.com/me`

**Request:**
```
GET https://graph.instagram.com/me
  ?fields=id,username,name,profile_picture_url,followers_count,media_count,account_type
  &access_token={access-token}
```

**Response:**
```json
{
  "id": "17841405793187218",
  "username": "your_business_account",
  "name": "Your Business Name",
  "profile_picture_url": "https://...",
  "followers_count": 1234,
  "media_count": 567,
  "account_type": "BUSINESS"
}
```

### 4. Exchange for Long-lived Token

**Endpoint**: `https://graph.instagram.com/access_token`

**Request:**
```
GET https://graph.instagram.com/access_token
  ?grant_type=ig_exchange_token
  &client_secret={app-secret}
  &access_token={short-lived-token}
```

**Response:**
```json
{
  "access_token": "IGQVJ...",
  "token_type": "bearer",
  "expires_in": 5184000
}
```

(60 days = 5,184,000 seconds)

## Important ID Clarification

**The `user_id` from OAuth IS the Instagram Business Account ID!**

From the guide's database model:
```python
instagram_user_id = Column(String, nullable=False)  # The actual Instagram account ID
instagram_business_account_id = Column(String, nullable=False)  # Same as user_id
```

These are populated with the SAME value - the `id` returned from OAuth.

## Webhook Integration

**Webhook `recipient_id` = OAuth `user_id`**

The Instagram Business Account ID returned in OAuth is the same ID used in webhook payloads as `recipient.id`.

## Account Type Field

The API returns `account_type` field with possible values:
- `BUSINESS` - Business account
- `CREATOR` - Creator account
- `PERSONAL` - Personal account (cannot use this API)

## Key Takeaways

1. ✅ **NO Facebook Page required** for Instagram Business Login
2. ✅ **OAuth `user_id` = Webhook `recipient_id`** (same ID!)
3. ✅ **Use `graph.instagram.com`** not `graph.facebook.com`
4. ✅ **Different scopes** than Facebook Login approach
5. ✅ **Direct account access** without Facebook Pages API

## References

- Full Guide: https://gist.github.com/PrenSJ2/0213e60e834e66b7e09f7f93999163fc
- Official Docs: https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/
