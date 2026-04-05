# Facebook OAuth Setup Guide

## Overview

This guide explains how to set up **one-click Facebook OAuth** for your e-commerce CS agent. Page owners can now connect their Facebook page without touching any code or API tokens.

## Why OAuth Instead of Manual Tokens?

### ❌ Old Way (Manual Tokens)
- Page owner must go to Facebook Developer Console
- Create an app
- Get Page Access Token manually
- Copy/paste tokens into your system
- **Non-technical users can't do this**

### ✅ New Way (OAuth Flow)
1. User clicks "Connect My Facebook Page"
2. Facebook login popup appears
3. User approves permissions
4. **Done!** Everything is automatic

## Setup Steps

### 1. Create Facebook App (One-time setup)

1. Go to [Facebook Developers](https://developers.facebook.com)
2. Click "My Apps" → "Create App"
3. Choose "Business" type
4. Fill in app details:
   - **App Name**: "YourBusiness CS Agent"
   - **App Contact Email**: your@email.com

### 2. Configure Facebook App

#### A. Add Products
1. In your app dashboard, add these products:
   - **Facebook Login**
   - **Webhooks**

#### B. Configure Facebook Login
1. Go to **Facebook Login** → **Settings**
2. Add **Valid OAuth Redirect URIs**:
   ```
   http://localhost:8000/api/auth/facebook/callback
   https://yourdomain.com/api/auth/facebook/callback
   ```
3. Save changes

#### C. Add Permissions
1. Go to **App Review** → **Permissions and Features**
2. Request these permissions:
   - `pages_show_list` - List user's pages
   - `pages_read_engagement` - Read messages
   - `pages_manage_metadata` - Subscribe webhooks
   - `pages_messaging` - Send messages
   - `pages_manage_posts` - Read posts for products

3. For each permission, click "Request Advanced Access" and provide use case

#### D. Get App Credentials
1. Go to **Settings** → **Basic**
2. Copy:
   - **App ID**
   - **App Secret**

### 3. Configure Your Backend

#### Update `.env` file:
```bash
# Facebook OAuth
FB_APP_ID=your_facebook_app_id_here
FB_APP_SECRET=your_app_secret_here
FB_VERIFY_TOKEN=your_custom_verify_token_123

# Your app URL (important for redirect)
APP_URL=https://yourdomain.com
```

#### If running locally:
```bash
FB_APP_ID=123456789
FB_APP_SECRET=abc123def456
APP_URL=http://localhost:8000
```

### 4. Configure Webhooks (For Messenger)

1. In Facebook App Dashboard, go to **Webhooks**
2. Click "Add Subscription" → Choose "Page"
3. Callback URL: `https://yourdomain.com/api/webhook`
4. Verify Token: (same as `FB_VERIFY_TOKEN` in your `.env`)
5. Subscribe to these fields:
   - `messages`
   - `messaging_postbacks`
   - `messaging_optins`
   - `message_deliveries`
   - `message_reads`

### 5. Test the Flow

#### Option A: Test Locally (with ngrok)
```bash
# Install ngrok
npm install -g ngrok

# Start your app
python run.py

# In another terminal, expose it
ngrok http 8000

# Update APP_URL in .env to ngrok URL
APP_URL=https://abc123.ngrok.io

# Update Facebook App redirect URI to:
https://abc123.ngrok.io/api/auth/facebook/callback
```

#### Option B: Test on Vercel
```bash
# Deploy to Vercel
vercel --prod

# Update APP_URL in Vercel environment variables
APP_URL=https://your-app.vercel.app

# Update Facebook App redirect URI to:
https://your-app.vercel.app/api/auth/facebook/callback
```

### 6. Share Onboarding Link

Send this link to page owners:
```
https://yourdomain.com/onboard
```

Or if local:
```
http://localhost:8000/onboard
```

## How the OAuth Flow Works

```
User (Page Owner)
    ↓
[Click "Connect My Facebook Page"]
    ↓
Your Backend: /api/auth/facebook/login
    ↓
[Redirect to Facebook OAuth]
    ↓
Facebook Login → User approves permissions
    ↓
[Facebook redirects back with code]
    ↓
Your Backend: /api/auth/facebook/callback
    ↓
[Exchange code for access token]
    ↓
[Get user's pages with Page Access Tokens]
    ↓
[Subscribe page to webhook]
    ↓
[Save seller + Page Access Token to database]
    ↓
[Scrape products from page]
    ↓
[Redirect to success page]
    ↓
Done! ✅
```

## API Endpoints

### `GET /api/auth/facebook/login`
Returns Facebook OAuth URL. Frontend redirects user here.

**Response:**
```json
{
  "auth_url": "https://facebook.com/v18.0/dialog/oauth?...",
  "message": "Redirect user to this URL"
}
```

### `GET /api/auth/facebook/callback`
Facebook redirects here after user authorizes. Handles token exchange and registration.

**Query Parameters:**
- `code` - Authorization code from Facebook
- `error` - Error if user declined

**Success:** Redirects to `/static/success.html` with seller details

**Error:** Returns HTTP error with message

## Troubleshooting

### Error: "Invalid OAuth redirect URI"
- Make sure your redirect URI in Facebook App matches exactly
- Check `APP_URL` in `.env` is correct
- Don't forget `/api/auth/facebook/callback` at the end

### Error: "App Not Set Up"
- Complete App Review for required permissions
- Make sure app is not in Development Mode for production
- Add test users if testing in Development Mode

### Error: "No pages found"
- User must be admin of a Facebook page
- User needs to create a page first
- Check if user approved `pages_show_list` permission

### Error: "Failed to subscribe webhook"
- Verify webhook is configured in Facebook App
- Check `FB_VERIFY_TOKEN` matches in both places
- Make sure your webhook endpoint is accessible

### User sees permissions but can't proceed
- App might be in Development Mode
- Add user as Test User or switch to Live Mode
- Complete App Review process

## Security Notes

1. **Never expose `FB_APP_SECRET`** in frontend code
2. Store Page Access Tokens securely in database
3. Use HTTPS in production (required by Facebook)
4. Validate webhook signatures using `FB_APP_SECRET`
5. Implement rate limiting on OAuth endpoints
6. Add CSRF protection if needed

## Production Checklist

- [ ] Facebook App is in **Live Mode**
- [ ] All required permissions have **Advanced Access**
- [ ] App Review is complete
- [ ] Webhook is configured and verified
- [ ] `APP_URL` points to production domain
- [ ] Redirect URIs include production URL
- [ ] HTTPS is enabled
- [ ] Environment variables are set correctly
- [ ] Database is ready (PostgreSQL recommended)
- [ ] Error handling and logging in place

## Next Steps

After successful OAuth:
1. **Dashboard**: Show seller their connected page
2. **Test Messages**: Send test message from Messenger
3. **Monitor**: Check logs for incoming webhooks
4. **Products**: Verify products are scraped correctly
5. **Billing**: Implement trial expiry and payment flow

## Resources

- [Facebook Login Documentation](https://developers.facebook.com/docs/facebook-login)
- [Messenger Platform Docs](https://developers.facebook.com/docs/messenger-platform)
- [Webhooks Setup](https://developers.facebook.com/docs/messenger-platform/webhooks)
- [Page Access Tokens](https://developers.facebook.com/docs/pages/access-tokens)
