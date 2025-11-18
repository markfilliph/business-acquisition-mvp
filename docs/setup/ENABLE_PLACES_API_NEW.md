# Enable Google Places API (New) - Step-by-Step Guide

## 🎯 Current Situation

You have **legacy Google Maps Places API** enabled, but we need **Places API (New)** which is a **separate service**.

**Error you're seeing:**
```
Places API (New) has not been used in project 746382517101 before or it is disabled
```

## 📋 Step-by-Step Instructions

### Step 1: Go to Google Cloud Console

**Direct Link to Enable Places API (New):**
```
https://console.cloud.google.com/marketplace/product/google/places-backend.googleapis.com?project=746382517101
```

OR manually:

1. Go to: https://console.cloud.google.com/
2. Select your project: **746382517101**
3. Click the menu (☰) → **APIs & Services** → **Library**

### Step 2: Search for "Places API (New)"

In the API Library search box, type:
```
Places API
```

You should see TWO different APIs:
- ❌ **Places API** (Legacy) - You already have this enabled
- ✅ **Places API (New)** - This is what you need

**Important:** Make sure you select the one that says **(New)** or shows the service name `places.googleapis.com`

### Step 3: Enable the API

1. Click on **Places API (New)**
2. Click the blue **ENABLE** button
3. Wait for confirmation (usually instant)

### Step 4: Verify Billing is Enabled

The new API requires billing to be enabled:

1. Go to: https://console.cloud.google.com/billing/projects
2. Make sure your project **746382517101** has a billing account linked
3. If not, click **LINK A BILLING ACCOUNT**

### Step 5: Wait 2-5 Minutes

After enabling, Google needs 2-5 minutes to propagate the changes across their systems.

### Step 6: Test the API

Run this command to test if it's working:

```bash
PYTHONPATH=/mnt/d/AI_Automated_Potential_Business_outreach ./venv/bin/python -c "
import asyncio
from src.sources.google_places import GooglePlacesSource

async def test():
    source = GooglePlacesSource()
    businesses = await source.fetch_businesses(
        location='Hamilton, ON',
        industry='manufacturing',
        max_results=5
    )

    if len(businesses) > 0:
        print(f'✅ SUCCESS! Found {len(businesses)} businesses')
        for biz in businesses[:3]:
            print(f'  - {biz.name}')
            print(f'    Phone: {biz.phone or \"N/A\"}')
            print(f'    Website: {biz.website or \"N/A\"}')
    else:
        print('❌ Still not working - wait a few more minutes')

asyncio.run(test())
"
```

## 🔍 Troubleshooting

### If you still see the error after 5 minutes:

1. **Check you enabled the RIGHT API:**
   - Go to: https://console.cloud.google.com/apis/dashboard?project=746382517101
   - Look for **"Places API (New)"** or **"places.googleapis.com"** in the list
   - If you only see "Places API" (without "New"), you enabled the wrong one

2. **Check billing is enabled:**
   - The new API requires a billing account
   - Even with free tier credits, billing must be enabled

3. **Check API restrictions on your key:**
   - Go to: https://console.cloud.google.com/apis/credentials?project=746382517101
   - Click on your API key
   - Under "API restrictions", make sure "Places API (New)" is allowed

## 💰 Pricing for Places API (New)

- **Text Search**: $0.032 per request
- **Free tier**: $200 monthly credit (covers ~6,250 searches)
- **For 100 businesses**: ~$3.20

## ✅ What You'll Get

Once enabled, you'll get **complete business data** in one request:

```
✅ Business name
✅ Full address (street, city, postal code)
✅ Phone number (direct from Google)
✅ Website URL
✅ GPS coordinates
✅ Business categories/types
✅ Business status (operational/closed)
```

## 🆚 Comparison

| Feature | OpenStreetMap (Current) | Places API (New) |
|---------|-------------------------|------------------|
| Business Names | ✅ Real | ✅ Real |
| Addresses | ✅ Real | ✅ Real (better quality) |
| Phone Numbers | 📊 Some (18/20) | ✅ All (~95%) |
| Websites | ✅ Real | ✅ Real |
| Data Freshness | Medium | High |
| Coverage | Good | Excellent |
| Cost | FREE | $0.032/business |

## 🎯 Expected Results After Enabling

You should be able to fetch **20-50 qualified B2B leads** with:
- ✅ Complete contact information
- ✅ High data quality (90%+ accuracy)
- ✅ Recent/fresh business data
- 📊 Employee ranges (industry averages)
- 📊 Revenue ranges (estimated)
- ❓ Website age (still needs WHOIS - separate task)

---

**Next Steps After Enabling:**
1. Wait 2-5 minutes
2. Run the test command above
3. If successful, run: `./venv/bin/python src/pipeline/smart_discovery_pipeline.py`
4. You should get 20+ qualified leads with complete contact data
