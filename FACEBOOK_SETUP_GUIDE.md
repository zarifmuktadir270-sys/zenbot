# Facebook Messenger Chatbot Setup — Complete Step-by-Step

Follow every step exactly. This takes about 30-40 minutes the first time.

---

## PART 1: CREATE A FACEBOOK PAGE (Skip if you already have one)

You need a Facebook Page for the bot to live on. This is the page customers will message.

### Steps:

1. Open Facebook: https://www.facebook.com
2. Click the menu (9 dots icon, top-left) or go to: https://www.facebook.com/pages/create
3. Choose **"Business or Brand"**
4. Fill in:
   - Page Name: Your shop name (e.g., "Fatema Fashion House")
   - Category: Search "Shopping & Retail" or "Clothing Store"
   - Bio: Short description of your shop
5. Click **"Create Page"**
6. Add a profile picture and cover photo (optional for now)
7. **IMPORTANT** — Get your Page ID:
   - Go to your page
   - Click **"About"** (left sidebar)
   - Scroll down to find **"Page ID"** (a number like `123456789012345`)
   - **SAVE THIS NUMBER** — you need it later

---

## PART 2: CREATE A FACEBOOK DEVELOPER ACCOUNT

### Steps:

1. Go to: https://developers.facebook.com
2. Click **"Get Started"** (top-right)
3. Log in with your personal Facebook account (the one that manages the Page)
4. You'll see a form asking:
   - "What do you need Facebook for?" → Select **"Build connected experiences"**
5. Accept the Terms
6. Verify your account:
   - Enter your phone number
   - Enter the code they text you
7. Done — you now have a Developer account

---

## PART 3: CREATE A FACEBOOK APP

This is the app that connects your server to Facebook Messenger.

### Steps:

1. Go to: https://developers.facebook.com/apps
2. Click **"Create App"** (green button, top-right)

3. **Screen 1 — "What do you want your app to do?"**
   - Select **"Other"**
   - Click **"Next"**

4. **Screen 2 — "Select an app type"**
   - Select **"Business"**
   - Click **"Next"**

5. **Screen 3 — "Provide basic information"**
   - App name: `EcomCSBot` (or any name you want)
   - App contact email: your email
   - Business Account: Select your business account (or "I don't want to connect a business portfolio yet")
   - Click **"Create App"**

6. Enter your Facebook password to confirm
7. You're now in the **App Dashboard**

### Get Your App Secret (You Need This):

1. In the App Dashboard, click **"Settings"** in the left sidebar
2. Click **"Basic"**
3. You'll see:
   - **App ID**: A number (e.g., `1234567890123456`)
   - **App Secret**: Click **"Show"**, enter password
   - **SAVE BOTH** — you need these

---

## PART 4: ADD MESSENGER TO YOUR APP

### Steps:

1. In your App Dashboard, scroll down to **"Add Products to Your App"**
   - Or click **"Add Product"** in the left sidebar
2. Find **"Messenger"**
3. Click **"Set Up"**
4. Messenger is now added — you'll see **"Messenger > Settings"** in the left sidebar

---

## PART 5: CONNECT YOUR PAGE + GET ACCESS TOKEN

This is the most critical step — the token lets your bot send messages on behalf of the page.

### Steps:

1. In the left sidebar, click **"Messenger"** → **"Settings"**

2. Scroll down to the **"Access Tokens"** section

3. Click **"Add or Remove Pages"**
   - A popup opens asking to log in
   - Log in with the Facebook account that MANAGES the page
   - Select the page you want to connect (e.g., "Fatema Fashion House")
   - Check the box next to the page
   - Click **"Next"**
   - You'll see permissions — toggle them ALL on:
     - "Manage and access Page conversations in Messenger" — YES
     - "Read content posted on the Page" — YES
     - "Manage accounts, settings and webhooks for a Page" — YES
   - Click **"Done"**
   - Click **"OK"** on the confirmation

4. Back on the Messenger Settings page, you'll see your page listed under "Access Tokens"

5. Click **"Generate Token"** next to your page name
   - A popup appears with the token
   - Check "I Understand"
   - Click **"Copy"**
   - **THIS IS YOUR `FB_PAGE_ACCESS_TOKEN`** — Save it! It's very long (starts with `EAA...`)

### IMPORTANT NOTES:
- This token does NOT expire (it's a long-lived page token)
- Keep it SECRET — anyone with this token can message from your page
- If you lose it, just come back here and generate a new one

---

## PART 6: SET UP THE WEBHOOK

The webhook tells Facebook: "When a customer messages this page, send the message to MY server."

### Prerequisites:
- Your server must be deployed and running first
- You need your server URL (e.g., `https://ecom-cs-agent.vercel.app`)

### Steps:

1. In Messenger Settings, scroll down to the **"Webhooks"** section

2. Click **"Add Callback URL"**

3. Fill in two fields:
   - **Callback URL**: `https://YOUR-VERCEL-URL.vercel.app/webhook`
     - Replace `YOUR-VERCEL-URL` with your actual Vercel domain
     - Must be `https://` (not `http://`)
   - **Verify Token**: `my_secret_verify_token_2024`
     - This must EXACTLY match what you set in Vercel's environment variables as `FB_VERIFY_TOKEN`
     - You can make this anything you want, just make sure both sides match

4. Click **"Verify and Save"**

5. **What happens:**
   - Facebook sends a GET request to your URL with the verify token
   - Your server checks if the token matches
   - If it matches, it returns the challenge → Facebook shows a green checkmark
   - If it fails → see Troubleshooting section below

6. After verification succeeds:
   - You'll see **"Add Subscriptions"** button next to your page
   - Click it
   - Check these boxes:
     - **messages** — When someone sends a message to your page
     - **messaging_postbacks** — When someone clicks a button
   - Click **"Save"**

### DONE! Your webhook is connected.

---

## PART 7: TEST YOUR BOT

### Quick Test:

1. Open your Facebook Page in a NEW browser tab (or use another Facebook account)
2. Click **"Message"** on the page
3. Type: **"Hi"**
4. Wait 2-5 seconds
5. The AI bot should reply!

### If It Works:
- Congratulations! Your bot is live.
- Try these messages:
  - "ki ki product ache?"
  - "saree er price koto?"
  - "order dite chai"

### If It Doesn't Work:
See Troubleshooting (Part 10 below)

---

## PART 8: SUBMIT FOR APP REVIEW (Required for Public Use)

Right now, your bot ONLY works for:
- Page admins
- App developers
- People you add as "Testers"

To make it work for ALL customers, you need Facebook's approval.

### Steps:

1. Go to: App Dashboard → **"App Review"** → **"Permissions and Features"**

2. Find **"pages_messaging"**
   - Click **"Request Advanced Access"**

3. You need to submit:

   **a) App Verification:**
   - Go to Settings → Basic
   - Fill in ALL required fields:
     - Privacy Policy URL (create a simple one at freeprivacypolicy.com)
     - App icon
     - Category: "Business and Pages"

   **b) Business Verification (if required):**
   - Facebook may ask you to verify your business
   - You'll need: Business name, address, phone, documents

   **c) Screencast (Video Recording):**
   - Record a 2-3 minute video showing:
     1. A customer messaging the page
     2. The bot replying automatically
     3. The bot answering product questions
     4. The bot taking an order
   - Use a screen recorder (OBS Studio is free, or just use your phone)
   - Upload to YouTube (unlisted) or share the video file

   **d) Description:**
   Write something like:
   > "Our app provides AI-powered customer service for e-commerce sellers on Facebook.
   > When a customer messages a seller's page, our bot automatically answers questions
   > about products, prices, delivery, and helps customers place orders. This improves
   > response time and helps sellers manage customer inquiries 24/7."

4. Click **"Submit for Review"**

5. **Wait time:** 1-5 business days (usually 2-3 days)

### While Waiting — Add Test Users:

1. Go to: App Dashboard → **"Roles"** → **"Roles"**
2. Click **"Add Testers"**
3. Enter the Facebook usernames of your beta sellers
4. They can now use the bot on their pages

---

## PART 9: ADD MORE PAGES (FOR NEW SELLERS)

When you get a new seller as a customer, you need to connect their page too.

### Simple Way (You Do It For Them):

1. Ask the seller to make you an **Admin** of their Facebook Page
   - They go to: Page Settings → Page Roles → Add "You" as Admin
2. Go to: Facebook App → Messenger → Settings → Access Tokens
3. Click "Add or Remove Pages"
4. Select their page
5. Generate token for their page
6. Register them via your API: POST /api/seller/register

### Better Way (Self-Serve — Build Later):

Build a sign-up page with "Login with Facebook" that:
1. Asks seller to log in with Facebook
2. Gets their page access token via OAuth
3. Auto-registers them
4. Starts working immediately

(This requires building a web frontend — do this after you have 20+ sellers)

---

## PART 10: TROUBLESHOOTING

### "Webhook verification failed"

**Cause 1: Server not running**
- Check: Visit `https://YOUR-URL.vercel.app/health`
- Should show: `{"status": "healthy"}`
- Fix: Check Vercel deployment logs

**Cause 2: Verify token mismatch**
- The token in Facebook MUST exactly match `FB_VERIFY_TOKEN` in Vercel env vars
- Case-sensitive, space-sensitive
- Fix: Copy-paste both values to make sure they're identical

**Cause 3: URL is wrong**
- Must be: `https://YOUR-URL.vercel.app/webhook` (not `/webhook/` with trailing slash)
- Must start with `https://`
- Fix: Double-check the URL

**Cause 4: Server returns error**
- Check Vercel logs: Vercel Dashboard → your project → Functions → Logs
- Common issue: database connection failing
- Fix: Make sure DATABASE_URL is correct in Vercel env vars

---

### "Bot is not replying to messages"

**Check 1: Webhook subscriptions**
- Go to: Messenger → Settings → Webhooks
- Make sure "messages" is checked for your page
- Fix: Click "Add Subscriptions" and check "messages"

**Check 2: Page is connected**
- Go to: Messenger → Settings → Access Tokens
- Your page should be listed
- Fix: Re-add the page

**Check 3: Environment variables**
- Vercel Dashboard → Settings → Environment Variables
- All 5 should be set:
  - FB_PAGE_ACCESS_TOKEN
  - FB_VERIFY_TOKEN
  - FB_APP_SECRET
  - ANTHROPIC_API_KEY
  - DATABASE_URL
- Fix: Add any missing variables, then redeploy

**Check 4: Anthropic API key**
- Go to: console.anthropic.com
- Make sure your key is active and has credits
- Fix: Add $5 credits and try again

**Check 5: Echo messages**
- If you message from the same account that manages the page, Facebook sends "echo" messages
- The bot ignores echoes (correct behavior)
- Fix: Test from a DIFFERENT Facebook account

---

### "Bot replies but in wrong language"

- The AI automatically matches the customer's language
- If customer writes Bangla → bot replies in Bangla
- If customer writes English → bot replies in English
- If customer writes Banglish → bot replies in Banglish
- If it's not matching correctly, the Claude AI prompt can be tuned in: `app/services/ai_agent.py`

---

### "Products not found"

**Check 1: Products were scraped**
- Visit: `https://YOUR-URL.vercel.app/api/seller/SELLER_ID/products`
- If empty: products weren't scraped from the Facebook page

**Check 2: Facebook posts have product keywords**
- Posts MUST contain words like: price, tk, taka, BDT, order, stock, size, delivery
- Posts without these keywords are skipped (assumed to be non-product posts)

**Check 3: Manual refresh**
- POST `https://YOUR-URL.vercel.app/api/seller/SELLER_ID/refresh-products`
- This forces a re-scrape of the Facebook page

---

### "Facebook App Review rejected"

Common rejection reasons:

1. **"Insufficient screencast"** → Re-record with clearer demo, show all features
2. **"No privacy policy"** → Add a privacy policy URL to App Settings
3. **"Unclear use case"** → Rewrite description to be more specific
4. **"App doesn't work"** → Make sure bot is working during review period

Tips for approval:
- Keep the demo video simple and clear
- Show real conversations (not just "hi" → "hello")
- Mention that you provide customer service, not spam
- Respond quickly if Facebook asks follow-up questions

---

## SUMMARY: ALL THE VALUES YOU NEED TO SAVE

| Value | Where to Find It | Used For |
|-------|-------------------|----------|
| **Page ID** | Facebook Page → About → Page ID | Registering seller |
| **App ID** | App Dashboard → Settings → Basic | Reference |
| **App Secret** | App Dashboard → Settings → Basic → Show | `FB_APP_SECRET` env var |
| **Page Access Token** | Messenger Settings → Access Tokens → Generate | `FB_PAGE_ACCESS_TOKEN` env var |
| **Verify Token** | You make this up (any string) | `FB_VERIFY_TOKEN` env var |
| **Anthropic API Key** | console.anthropic.com → API Keys | `ANTHROPIC_API_KEY` env var |
| **Database URL** | Supabase → Settings → Database → URI | `DATABASE_URL` env var |

Save all of these in a secure place (password manager or encrypted note).

---

*Follow these steps in order and you'll have a working AI chatbot on Facebook Messenger in under an hour.*
