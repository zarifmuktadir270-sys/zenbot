# Step-by-Step: Deploy AI Chatbot on Facebook Messenger

This guide takes you from ZERO to a working AI chatbot on a Facebook Page.
No prior coding experience needed — just follow each step.

---

## OVERVIEW: How It Works

```
Customer sends message on Facebook Page
        ↓
Facebook sends it to YOUR server (webhook)
        ↓
Your server sends it to Claude AI
        ↓
Claude reads the shop's products + policies and writes a reply
        ↓
Your server sends the reply back via Messenger
        ↓
Customer sees the reply instantly
```

**Total setup time: 2-3 hours** (first time, slower; after that, 30 min per new seller)

---

## PHASE 1: GET YOUR ACCOUNTS READY

### Step 1.1: Get Anthropic API Key (Claude AI)

1. Go to: https://console.anthropic.com
2. Click "Sign Up" — create an account with email
3. Add payment method (credit/debit card)
4. Go to "API Keys" in the left menu
5. Click "Create Key"
6. Copy the key — it looks like: `sk-ant-api03-xxxxxxxxxxxx`
7. Save it somewhere safe (Notepad)

**Cost**: About $5-10/month for 50 sellers. You pay per message processed.

### Step 1.2: Create a Facebook Developer Account

1. Go to: https://developers.facebook.com
2. Click "Get Started"
3. Log in with your personal Facebook account
4. Accept the developer terms
5. Verify your account (phone number or email)

**Cost**: Free

### Step 1.3: Get a Server (Railway — Easiest Option)

1. Go to: https://railway.com
2. Sign up with GitHub account
3. That's it for now — we'll deploy later

**Cost**: ~$5/month (free trial available)

### Step 1.4: Get a Database (Supabase — Free)

1. Go to: https://supabase.com
2. Sign up (free)
3. Click "New Project"
4. Name: `ecom-cs-agent`
5. Set a database password — SAVE THIS
6. Region: Choose closest to Bangladesh (Singapore)
7. Click "Create Project"
8. Once created, go to: Settings → Database
9. Copy the "Connection string (URI)" — it looks like:
   `postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres`
10. Save this — this is your `DATABASE_URL`

**Cost**: Free (up to 500MB, enough for 1000+ sellers)

---

## PHASE 2: CREATE A FACEBOOK APP

This is the most important part. Pay close attention.

### Step 2.1: Create the App

1. Go to: https://developers.facebook.com/apps
2. Click **"Create App"**
3. Choose **"Other"** as use case
4. Choose **"Business"** as app type
5. App name: `EcomCSAgent` (or your business name)
6. Click **"Create App"**

### Step 2.2: Add Messenger Product

1. In your app dashboard, find **"Add Products"** section
2. Find **"Messenger"** and click **"Set Up"**
3. You'll see the Messenger Settings page

### Step 2.3: Connect a Facebook Page

You need a Facebook Page for the chatbot to work on. This can be:
- Your OWN test page (for testing)
- Your CLIENT'S page (for production)

**To connect:**
1. In Messenger Settings, scroll to **"Access Tokens"**
2. Click **"Add or Remove Pages"**
3. Log in and select the page you want to connect
4. Grant all permissions when asked
5. After connecting, click **"Generate Token"** next to the page name
6. Copy this token — this is `FB_PAGE_ACCESS_TOKEN`
7. **SAVE THIS TOKEN** — you'll need it

### Step 2.4: Set Up the Webhook (We'll Complete This After Deploying)

We need to deploy the server first, then come back here. Skip this for now.

---

## PHASE 3: DEPLOY THE SERVER

### Step 3.1: Get the Code on GitHub

**Option A: If you know Git**
1. Create a new GitHub repository
2. Push the `ecom-cs-agent` folder to it

**Option B: If you don't know Git**
1. Go to: https://github.com/new
2. Name: `ecom-cs-agent`
3. Click "Create Repository"
4. Click "uploading an existing file"
5. Drag and drop ALL files from the `ecom-cs-agent` folder
6. Click "Commit changes"

### Step 3.2: Deploy on Railway

1. Go to: https://railway.com/new
2. Click **"Deploy from GitHub Repo"**
3. Select your `ecom-cs-agent` repository
4. Railway will start building — wait for it

### Step 3.3: Add Environment Variables

1. In Railway, click on your service
2. Go to **"Variables"** tab
3. Add these variables one by one:

```
FB_PAGE_ACCESS_TOKEN = (the token from Step 2.3)
FB_VERIFY_TOKEN = my_secret_verify_token_2024
FB_APP_SECRET = (from Facebook App → Settings → Basic → App Secret)
ANTHROPIC_API_KEY = (from Step 1.1)
DATABASE_URL = (from Step 1.4)
```

**To find FB_APP_SECRET:**
1. Go to your Facebook App → Settings → Basic
2. Click "Show" next to App Secret
3. Enter your Facebook password
4. Copy the secret

4. Click **"Deploy"** to restart with the new variables

### Step 3.4: Get Your Server URL

1. In Railway, go to **"Settings"** tab
2. Under **"Networking"**, click **"Generate Domain"**
3. You'll get a URL like: `ecom-cs-agent-production.up.railway.app`
4. Test it: Open `https://YOUR-URL.up.railway.app/health` in browser
5. You should see: `{"status": "healthy"}`

**Save this URL — you need it next.**

---

## PHASE 4: CONNECT FACEBOOK TO YOUR SERVER

### Step 4.1: Configure the Webhook

1. Go back to: https://developers.facebook.com/apps → Your App → Messenger → Settings
2. Scroll to **"Webhooks"** section
3. Click **"Add Callback URL"**
4. Fill in:
   - **Callback URL**: `https://YOUR-URL.up.railway.app/webhook`
   - **Verify Token**: `my_secret_verify_token_2024` (must match what you set in Railway)
5. Click **"Verify and Save"**
6. If it shows a green checkmark — it worked!

**If it fails:**
- Check your server is running (visit /health URL)
- Check the verify token matches EXACTLY
- Make sure URL starts with `https://`

### Step 4.2: Subscribe to Messages

1. Still on the Webhooks section
2. Click **"Add Subscriptions"** next to your page
3. Check these boxes:
   - **messages** (customer messages)
   - **messaging_postbacks** (button clicks)
4. Click **"Save"**

### Step 4.3: Test It!

1. Go to your Facebook Page
2. Click **"Message"** (or ask a friend to message)
3. Type: "Hi"
4. Wait 2-5 seconds...
5. The AI should reply!

**If the bot doesn't reply:**
- Check Railway logs (Railway → your service → "Logs" tab)
- Make sure all environment variables are set correctly
- Make sure webhook subscriptions are active

---

## PHASE 5: REGISTER YOUR FIRST SELLER

### Step 5.1: Register via API

Open your browser or use any API tool (like Postman, or just use the built-in docs):

1. Go to: `https://YOUR-URL.up.railway.app/docs`
2. This opens the API documentation
3. Find **POST /api/seller/register**
4. Click "Try it out"
5. Fill in:

```json
{
  "fb_page_id": "YOUR_PAGE_ID",
  "fb_page_name": "Your Shop Name",
  "fb_page_access_token": "YOUR_PAGE_TOKEN",
  "delivery_info": "Dhaka: 60 BDT, Outside Dhaka: 120 BDT",
  "payment_methods": "bKash, Nagad, COD",
  "delivery_time": "Dhaka: 1-2 din, Outside: 3-5 din",
  "return_policy": "7 din er moddhe return korte parben"
}
```

**To find your PAGE_ID:**
1. Go to your Facebook Page
2. Click "About"
3. Scroll down — you'll see "Page ID"
4. Or: Go to Facebook App → Messenger Settings → you'll see it next to the page name

6. Click "Execute"
7. You should see: `"Found X products from your page"`

### Step 5.2: Verify Products Were Scraped

1. In the API docs, find **GET /api/seller/{seller_id}/products**
2. Enter your seller_id (from the registration response)
3. Click "Execute"
4. You should see your products listed

### Step 5.3: Test the Full Flow

1. Go to your Facebook Page
2. Message it as a customer would:
   - "Hi, ki ki product ache?"
   - "ei dress er price koto?"
   - "order dite chai"
3. The AI should respond naturally in the same language!

---

## PHASE 6: GO LIVE (For Real Customers)

### Step 6.1: Submit App for Review

Facebook requires app review before your bot can message the public.

1. Go to: Facebook App → App Review → Permissions and Features
2. Request these permissions:
   - **pages_messaging** — "To provide automated customer service on seller pages"
3. For the review:
   - Record a 2-minute screen recording showing the bot working
   - Explain: "We provide AI customer service for e-commerce sellers on Facebook"
   - Submit

**Review takes**: 1-5 business days

### Step 6.2: While Waiting for Review

During review, the bot works ONLY for:
- Page admins
- App admins and testers
- People you add as "Testers" in the app settings

**Add testers:**
1. Facebook App → Roles → Roles
2. Click "Add Testers"
3. Add your beta sellers' Facebook accounts

### Step 6.3: After Approval

Once approved:
- Your bot works for ALL customers who message the page
- No limits on number of messages
- You can connect multiple pages (one per seller)

---

## PHASE 7: ADD MORE SELLERS (Your Business Grows)

### For Each New Seller:

1. **Get their Page Access Token:**
   - They add your Facebook App to their page
   - Or: You use Facebook Login to get their token (advanced — requires building a sign-up page)

2. **Register them via API:**
   - POST /api/seller/register with their info

3. **Products auto-load** from their Facebook posts

4. **Bot starts working** on their page immediately

### Scaling Approach:

**5-20 sellers**: Manual registration via API (you do it for them)
**20-100 sellers**: Build a simple sign-up website
**100+ sellers**: Full self-serve onboarding with Facebook Login

---

## PHASE 8: CHARGING SELLERS (Making Money)

### Simple Payment Collection (Start Here):

1. **bKash/Nagad Manual**:
   - Send monthly invoice via WhatsApp
   - They send money to your bKash merchant number
   - You activate/deactivate in database

2. **Pricing Reminder**:
   - Starter: 2,999 BDT/month (1 page, 500 conversations)
   - Growth: 4,999 BDT/month (2 pages, 2000 conversations)
   - Pro: 9,999 BDT/month (unlimited)

### Later (When You Have 50+ Sellers):

- Build subscription management with SSLCommerz
- Auto-deactivate if payment is overdue
- Add usage-based billing

---

## TROUBLESHOOTING

### "Bot is not replying"

**Check 1: Server running?**
- Visit `https://YOUR-URL.up.railway.app/health`
- Should show `{"status": "healthy"}`

**Check 2: Webhook connected?**
- Facebook App → Messenger → Webhooks
- Should show green checkmark

**Check 3: Environment variables set?**
- Railway → Variables tab
- All 5 variables should be there

**Check 4: Subscription active?**
- Facebook App → Messenger → Webhooks
- "messages" should be checked for your page

**Check 5: Server logs**
- Railway → Logs tab
- Look for error messages

### "Bot replies in wrong language"

The AI automatically matches the customer's language. If it's replying in English to Bangla messages, the prompt might need tuning. Update the system prompt in `app/services/ai_agent.py`.

### "Products not showing"

1. Make sure your Facebook posts mention prices or product keywords
2. Try manual refresh: POST `/api/seller/{id}/refresh-products`
3. Check if Page Access Token is valid

### "Facebook webhook verification failed"

- Make sure `FB_VERIFY_TOKEN` in Railway matches EXACTLY what you entered in Facebook
- Make sure URL is `https://` (not `http://`)
- Make sure server is running

### "Rate limits"

- Facebook allows 250 API calls per hour per page
- Claude API has no strict rate limit (you pay per use)
- If you hit limits, add message queuing (Redis + Bull)

---

## FILE STRUCTURE

```
ecom-cs-agent/
├── app/
│   ├── __init__.py
│   ├── config.py              ← Settings (reads from .env)
│   ├── main.py                ← App entry point, scheduler
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py        ← Database connection
│   │   └── models.py          ← Seller, Product, Customer, Order tables
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── webhook.py         ← Facebook Messenger webhook (receives messages)
│   │   └── seller.py          ← Seller dashboard API
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ai_agent.py        ← Claude AI brain (processes messages)
│   │   └── page_scraper.py    ← Scrapes products from Facebook page
│   └── utils/
│       ├── __init__.py
│       └── facebook.py        ← Sends messages via Messenger API
├── .env.example               ← Environment variable template
├── Dockerfile                 ← For deployment
├── railway.json               ← Railway deployment config
├── requirements.txt           ← Python dependencies
└── run.py                     ← Local development runner
```

---

## COST BREAKDOWN (Monthly)

### For 10 Sellers:
| Item | Cost |
|------|------|
| Railway (server) | $5 (~600 BDT) |
| Supabase (database) | Free |
| Claude API (~3000 messages) | $8 (~950 BDT) |
| Facebook API | Free |
| **Total** | **~1,550 BDT/month** |
| **Revenue** (10 × 2,999) | **29,990 BDT/month** |
| **Profit** | **~28,400 BDT/month** |

### For 50 Sellers:
| Item | Cost |
|------|------|
| Railway (server) | $10 (~1,200 BDT) |
| Supabase (database) | $25 (~3,000 BDT) |
| Claude API (~15000 messages) | $40 (~4,800 BDT) |
| Facebook API | Free |
| **Total** | **~9,000 BDT/month** |
| **Revenue** (50 × 3,500 avg) | **1,75,000 BDT/month** |
| **Profit** | **~1,66,000 BDT/month** |

### For 200 Sellers:
| Item | Cost |
|------|------|
| Railway/AWS | $50 (~6,000 BDT) |
| Database | $50 (~6,000 BDT) |
| Claude API | $150 (~18,000 BDT) |
| **Total** | **~30,000 BDT/month** |
| **Revenue** (200 × 4,000 avg) | **8,00,000 BDT/month** |
| **Profit** | **~7,70,000 BDT/month** |

---

## WHAT TO DO NEXT (Your Action Items)

### This Week:
- [ ] Create Anthropic account and get API key
- [ ] Create Facebook Developer account
- [ ] Create a test Facebook Page (for testing)
- [ ] Create Supabase database

### Next Week:
- [ ] Create Facebook App
- [ ] Deploy code on Railway
- [ ] Connect webhook
- [ ] Test with your own page

### Week 3:
- [ ] Find 3-5 Facebook sellers willing to try for free
- [ ] Register them as sellers
- [ ] Monitor conversations and fix issues

### Week 4:
- [ ] Collect testimonials from beta sellers
- [ ] Set up pricing and bKash payment
- [ ] Start Facebook ads targeting sellers

---

*You now have everything you need. The code is ready. The guide is complete. Go build it.*
