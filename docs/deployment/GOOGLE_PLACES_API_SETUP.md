# Google Places API Setup Guide

**Purpose**: Enable business discovery using Google Places API
**Cost**: FREE ($200 monthly credit = ~28,000 searches)
**Time**: 10-15 minutes
**Date**: October 12, 2025

---

## Step 1: Create Google Cloud Account

### 1.1 Go to Google Cloud Console
- **URL**: https://console.cloud.google.com/
- Click **"Go to Console"** or **"Get Started for Free"**

### 1.2 Sign In
- Use your existing Google account (Gmail)
- Or create a new Google account if needed

### 1.3 Accept Terms
- Review and accept Google Cloud Platform Terms of Service
- Click **"AGREE AND CONTINUE"**

---

## Step 2: Create a New Project

### 2.1 Access Project Selector
- At the top of the console, click on the **project dropdown** (says "Select a project")
- Or look for the project name in the top navigation bar

### 2.2 Create New Project
- Click **"NEW PROJECT"** button (top right of dialog)
- **Project name**: `Business-Lead-Generator` (or any name you prefer)
- **Organization**: Leave as default (No organization)
- **Location**: Leave as default
- Click **"CREATE"**

### 2.3 Wait for Project Creation
- Takes 10-30 seconds
- You'll see a notification when ready
- Click **"SELECT PROJECT"** in the notification

---

## Step 3: Enable Billing (Required for API Access)

### 3.1 Go to Billing
- In the left menu, click **"Billing"**
- Or search for "Billing" in the top search bar

### 3.2 Link Billing Account
- Click **"LINK A BILLING ACCOUNT"**
- If you don't have one, click **"CREATE BILLING ACCOUNT"**

### 3.3 Enter Payment Information
- **Country**: Select your country
- **Account type**: Individual or Business
- **Payment method**: Credit/debit card
- Enter your card details
- Click **"START MY FREE TRIAL"**

**Note**: You get $200 FREE credit each month. You won't be charged unless you exceed this limit.

---

## Step 4: Enable Places API

### 4.1 Go to APIs & Services
- In the left menu (☰), navigate to:
  - **"APIs & Services"** → **"Library"**
- Or use the search bar at top: Search for **"API Library"**

### 4.2 Search for Places API
- In the API Library search box, type: **"Places API"**
- You'll see two options:
  - **Places API (New)** ← Use this one (recommended)
  - Places API (legacy)

### 4.3 Enable the API
- Click on **"Places API (New)"**
- Click the blue **"ENABLE"** button
- Wait 10-20 seconds for activation

**Confirmation**: You'll see "API enabled" with a green checkmark

---

## Step 5: Create API Key

### 5.1 Go to Credentials
- In the left menu, click **"Credentials"**
- Or navigate: **"APIs & Services"** → **"Credentials"**

### 5.2 Create Credentials
- Click **"+ CREATE CREDENTIALS"** at the top
- Select **"API key"** from the dropdown

### 5.3 Copy Your API Key
- A dialog will appear with your API key
- **IMPORTANT**: Copy this key immediately!
- It will look like: `AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`
- Click **"CLOSE"** (you can retrieve it later if needed)

---

## Step 6: Restrict API Key (Security - Recommended)

### 6.1 Click on Your API Key
- In the Credentials page, find your newly created API key
- Click on the **key name** (not the key itself)

### 6.2 Application Restrictions
- Scroll to **"Application restrictions"**
- Select **"IP addresses"**
- Click **"ADD AN ITEM"**
- Add your server's IP address
- Or select **"None"** for testing (less secure)

### 6.3 API Restrictions
- Scroll to **"API restrictions"**
- Select **"Restrict key"**
- Click **"Select APIs"** dropdown
- Check ✓ **"Places API (New)"**
- Uncheck all other APIs

### 6.4 Save Changes
- Click **"SAVE"** at the bottom
- Wait for the confirmation message

---

## Step 7: Add API Key to Your Project

### 7.1 Open .env File
```bash
cd /mnt/d/AI_Automated_Potential_Business_outreach
nano .env
```

Or use any text editor to open `.env` file in your project root.

### 7.2 Add/Update API Key
Add this line (replace with your actual key):
```bash
GOOGLE_MAPS_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

### 7.3 Save File
- Save and close the editor
- The system will automatically load this on next run

---

## Step 8: Verify Setup

### 8.1 Check Configuration
```bash
./venv/bin/python -c "from src.core.config import config; print('Google API Key:', 'SET' if config.google_api_key else 'NOT SET')"
```

**Expected output**: `Google API Key: SET`

### 8.2 Test API Access
```bash
./venv/bin/python -c "
from src.sources.places import PlacesService
import asyncio

async def test():
    places = PlacesService()
    result = await places.search_businesses('manufacturing', 'Hamilton, ON', max_results=1)
    print(f'✅ API Working! Found {len(result)} result(s)')

asyncio.run(test())
"
```

**Expected output**: `✅ API Working! Found 1 result(s)`

---

## Step 9: Generate Leads!

Now you can generate leads with Google Places as a data source:

```bash
# Generate 30 leads
./generate_v2 30 --show

# Generate 200 leads
./generate_v2 200
```

The system will now use Google Places API to discover businesses!

---

## Pricing & Quotas

### Free Tier
- **Monthly credit**: $200 FREE
- **Text Search**: $0.007 per request
- **Free searches**: ~28,000 per month
- **Your usage**: ~3000 searches = ~$21/month (covered by free credit)

### Rate Limits
- **Default**: 100 queries per second (QPS)
- **Your usage**: ~10 QPS (well under limit)

### Monitoring Usage
1. Go to: **"APIs & Services"** → **"Dashboard"**
2. View API usage metrics
3. Set up billing alerts (optional)

---

## Troubleshooting

### "API Key not valid"
- **Cause**: Key restrictions too strict or API not enabled
- **Fix**: Check that Places API (New) is enabled and key has access

### "This API project is not authorized"
- **Cause**: Billing not set up
- **Fix**: Complete Step 3 (Enable Billing)

### "The provided API key is invalid"
- **Cause**: Key copied incorrectly
- **Fix**: Copy the entire key including any trailing characters

### "Quota exceeded"
- **Cause**: Exceeded free tier ($200 credit)
- **Fix**: Wait for next month or add more credits

### Key Not Loading in Config
- **Check .env file exists**: `ls -la .env`
- **Check key is set**: `grep GOOGLE_MAPS_API_KEY .env`
- **Restart application**: Close and rerun `./generate_v2`

---

## Security Best Practices

### DO:
✅ Restrict API key to specific APIs only
✅ Restrict by IP address when possible
✅ Keep API key in .env file (never commit to git)
✅ Monitor usage regularly
✅ Set up billing alerts

### DON'T:
❌ Share API key publicly
❌ Commit API key to GitHub
❌ Use same key across multiple projects
❌ Leave unrestricted API keys active

---

## Alternative: Use Existing API Key

If you already have a Google Cloud project with Places API enabled:

1. Go to: https://console.cloud.google.com/apis/credentials
2. Find existing API key or create new one
3. Ensure **"Places API (New)"** is enabled
4. Copy key and add to `.env` file

---

## Quick Reference

**Console URL**: https://console.cloud.google.com/
**API Library**: https://console.cloud.google.com/apis/library
**Credentials**: https://console.cloud.google.com/apis/credentials
**Billing**: https://console.cloud.google.com/billing
**Pricing Calculator**: https://cloud.google.com/products/calculator

---

## Next Steps

Once API key is set up:

1. ✅ Test with: `./generate_v2 5 --show`
2. ✅ Generate full batch: `./generate_v2 200`
3. ✅ Review results in database
4. ✅ Export qualified leads

**Status**: Ready to generate leads! 🚀
