# Deploy to Vercel - Quick Guide

## ✅ Your App is Ready to Deploy!

All changes have been committed to git. Now let's deploy to Vercel.

## Option 1: Deploy via Vercel CLI (Fastest)

### Step 1: Get Your Vercel Token
1. Go to https://vercel.com/account/tokens
2. Click "Create Token"
3. Give it a name (e.g., "CS Agent Deploy")
4. Copy the token

### Step 2: Deploy
```bash
cd /home/vercel-sandbox/ecom-cs-agent
export VERCEL_TOKEN=your_token_here
vercel --yes --prod
```

## Option 2: Deploy via Vercel Dashboard (Easiest)

### Step 1: Push to GitHub (if not already)
```bash
# Create a new GitHub repo first, then:
git remote add origin https://github.com/yourusername/ecom-cs-agent.git
git push -u origin master
```

### Step 2: Import to Vercel
1. Go to https://vercel.com/new
2. Click "Import Git Repository"
3. Select your GitHub repo
4. Vercel will auto-detect the Python project
5. Click "Deploy"

### Step 3: Add Environment Variables
In Vercel Dashboard → Settings → Environment Variables, add:

```
FB_APP_ID=your_facebook_app_id
FB_APP_SECRET=your_facebook_app_secret
FB_VERIFY_TOKEN=your_verify_token_123
ANTHROPIC_API_KEY=your_anthropic_key
DATABASE_URL=your_postgres_url
APP_URL=https://your-app.vercel.app
```

**Important:** After deploying, update `APP_URL` with your actual Vercel URL.

## Option 3: Deploy from Local Machine

If you have the code on your local machine:

```bash
# Clone or download the code
cd ecom-cs-agent

# Install Vercel CLI
npm install -g vercel

# Login to Vercel
vercel login

# Deploy
vercel --prod
```

## After Deployment

### 1. Get Your Vercel URL
After deployment, you'll get a URL like:
```
https://ecom-cs-agent-abc123.vercel.app
```

### 2. Update Facebook App Settings
1. Go to Facebook App → Settings → Basic
2. Update **Valid OAuth Redirect URIs** to:
   ```
   https://your-vercel-url.vercel.app/api/auth/facebook/callback
   ```

3. Update **Webhook Callback URL** to:
   ```
   https://your-vercel-url.vercel.app/api/webhook
   ```

### 3. Update Environment Variable
In Vercel Dashboard, update:
```
APP_URL=https://your-vercel-url.vercel.app
```

### 4. Test It!
Visit:
```
https://your-vercel-url.vercel.app/onboard
```

You should see the beautiful onboarding page!

## Database Setup

Vercel's free tier doesn't include a database. You need to:

### Option A: Use Vercel Postgres (Recommended)
1. In Vercel Dashboard → Storage → Create Database
2. Select "Postgres"
3. Copy the connection string
4. Add to environment variables as `DATABASE_URL`

### Option B: Use Supabase (Free)
1. Go to https://supabase.com
2. Create new project
3. Get connection string from Settings → Database
4. Add to environment variables as `DATABASE_URL`

### Option C: Use Neon (Free)
1. Go to https://neon.tech
2. Create new project
3. Copy connection string
4. Add to environment variables as `DATABASE_URL`

## Troubleshooting

### "Token is not valid"
- Run `vercel login` to authenticate
- Or set `VERCEL_TOKEN` environment variable

### "Build failed"
- Check `requirements.txt` has all dependencies
- Check `vercel.json` configuration
- View build logs in Vercel dashboard

### "OAuth redirect URI mismatch"
- Make sure Facebook App redirect URI matches your Vercel URL exactly
- Include `/api/auth/facebook/callback` at the end

### "Environment variable not found"
- Go to Vercel Dashboard → Settings → Environment Variables
- Add all required variables
- Redeploy after adding variables

## Current Deployment Status

✅ Code committed to git (commit: 111e5bb)
⏳ Waiting for Vercel authentication
📦 Ready to deploy once authenticated

## Quick Commands Reference

```bash
# Deploy to production
vercel --prod

# Deploy to preview
vercel

# Check deployment status
vercel ls

# View logs
vercel logs

# Set environment variable
vercel env add DATABASE_URL
```

## Next Steps After Deployment

1. ✅ Test onboarding page
2. ✅ Connect a test Facebook page
3. ✅ Send test message from Messenger
4. ✅ Check webhook logs
5. ✅ Verify product scraping works
6. ✅ Set up database backups
7. ✅ Configure custom domain (optional)

---

**Need help?** Check the logs with `vercel logs` or contact support.
