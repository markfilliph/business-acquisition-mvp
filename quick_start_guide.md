# 🚀 Quick Start Guide - Fixed Lead Generation

Get your lead generation system working in 5 minutes!

## 📦 What You're Getting

**The Problem You Had:**
- Request 30 leads → Get 27 excluded, 3 qualified ❌

**The Solution:**
- Request 30 leads → Get exactly 30 qualified ✅

## ⚡ Installation (2 minutes)

### Step 1: Add New Files to Your Repo

Save these files to your repository:

```bash
# New files structure
business-acquisition-mvp/
├── scripts/
│   ├── lead_qualifier.py         # ← Main qualification script
│   └── automated_workflow.py     # ← Complete pipeline
├── requirements-file.txt          # ← Updated dependencies
├── CLAUDE_CODE_SETUP.md          # ← Claude Code integration
└── QUICKSTART.md                 # ← This file
```

### Step 2: Install Dependencies

```bash
# Activate your environment
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install updated packages
pip install -r requirements-file.txt
```

### Step 3: Verify Installation

```bash
# Test the qualifier script
python scripts/lead_qualifier.py --help

# You should see usage instructions
```

✅ **Installation complete!**

---

## 🎯 Usage (3 minutes)

### Option 1: Process Your Existing CSV

You have a CSV with mixed leads (your current file with 27 excluded, 10 review required).

```bash
python scripts/lead_qualifier.py \
    --input data/YOUR_CURRENT_FILE.csv \
    --target 30 \
    --output data/qualified_leads.csv
```

**What happens:**
1. Reads your CSV with all the excluded/review_required leads
2. Validates each lead against criteria
3. Estimates missing employee counts
4. Keeps processing until it has 30 qualified leads
5. Outputs TWO files:
   - `qualified_leads.csv` - 30 ready-to-contact leads
   - `qualified_leads_excluded.csv` - Rejected leads with reasons

### Option 2: Use the Complete Workflow

Automates the entire pipeline:

```bash
python scripts/automated_workflow.py \
    --input data/YOUR_CURRENT_FILE.csv \
    --target 30
```

**What happens:**
1. Qualifies leads
2. Updates your Google Sheets CRM (if configured)
3. Generates a report
4. Shows you next steps

---

## 🤖 Claude Code Usage (Easiest!)

If you have Claude Code installed:

```bash
# Start Claude Code
claude-code

# Then just tell it what you want:
> Process my leads in data/hamilton_leads.csv and get me 30 qualified companies with under 30 employees

# Or run the full workflow:
> Run the automated workflow to qualify 30 leads from my raw CSV and update the CRM
```

Claude Code will:
- Find your CSV files
- Run the right scripts
- Handle errors
- Show you results

---

## 📊 Understanding the Output

### Qualified Leads CSV

```csv
Company Name,Status,Phone,Website,Employee Count,Revenue Estimate,Exclusion Reason
Atlas Die,QUALIFIED,9055445000,https://atlasdie.com,15,"$750,000",
Burloak Tech,QUALIFIED,9056435551,https://burloaktech.com,22,"$1,100,000",
...
```

**Status = QUALIFIED** means ready for outreach!

### Excluded Leads CSV

```csv
Company Name,Status,Exclusion Reason
ArcelorMittal,EXCLUDED,"Too many employees (5000 > 30)"
BDO Canada,EXCLUDED,"Too many employees (60 > 30)"
...
```

Use this to:
- Understand why leads were rejected
- Adjust your criteria if needed
- Find patterns (e.g., "all manufacturing too large")

---

## 🔧 Common Adjustments

### "I Need More/Fewer Employees"

```bash
python scripts/lead_qualifier.py \
    --input data/leads.csv \
    --target 30 \
    --max-employees 50  # Increased from 30
```

### "My Revenue Range is Different"

```bash
python scripts/lead_qualifier.py \
    --input data/leads.csv \
    --target 30 \
    --min-revenue 500000 \
    --max-revenue 3000000
```

### "I Only Got 15 Qualified Leads, Not 30"

This means your source CSV doesn't have enough companies that meet your criteria.

**Solutions:**

1. **Relax criteria** (try 40 max employees instead of 30)
2. **Expand search area** (add Burlington, Oakville nearby)
3. **Get more raw leads** (fetch larger batch from Google Maps)

```bash
# Claude Code can help automate this:
claude-code
> I only got 15 leads but need 30. Help me find the right criteria or get more leads.
```

---

## 🎓 Real-World Example

### Your Current Situation

You have this CSV:

```csv
Company Name,Employee Count,Status
ArcelorMittal,5000,EXCLUDED
BDO Canada,60,EXCLUDED
Atlas Die,,REVIEW_REQUIRED
Burloak Tech,,REVIEW_REQUIRED
```

### Run the Qualifier

```bash
python scripts/lead_qualifier.py \
    --input data/current_leads.csv \
    --target 30
```

### What It Does

```
Processing leads...

❌ ArcelorMittal - Too many employees (5000 > 30)
❌ BDO Canada - Too many employees (60 > 30)
🔧 Atlas Die - Estimating employee count... 
✅ Atlas Die (estimated 15 employees)
🔧 Burloak Tech - Estimating employee count...
✅ Burloak Tech (estimated 22 employees)

Progress: 2/30 qualified
Need 28 more leads...
```

The script will keep processing until it finds 30 that qualify.

---

## 🔥 Integration with Your Existing Workflow

### Before (Your Old Process)

```
1. Fetch leads manually
2. Open in Excel
3. Manually filter out >30 employees
4. Realize you only have 3 qualified
5. Search for more leads
6. Repeat...
```

### After (New Process)

```
1. Fetch ANY leads to CSV (don't worry about filtering)
2. Run: python scripts/lead_qualifier.py --target 30
3. Get exactly 30 qualified leads
4. Continue with your email workflow
```

### Your Existing Scripts Still Work!

The qualified leads CSV works with your existing:
- ✅ `prospects_tracker.py` - Updates Google Sheets
- ✅ `email_sender.py` - Sends campaigns  
- ✅ `email_tracker.py` - Monitors responses
- ✅ All your other automation

**Nothing breaks!** You're just adding a qualification step.

---

## 💡 Pro Tips

### 1. Start Small

```bash
# Test with just 5 leads first
python scripts/lead_qualifier.py --input data/test.csv --target 5
```

Verify it works, then scale to 30.

### 2. Review Excluded Leads

```bash
# Look at why leads were excluded
cat data/qualified_leads_excluded.csv | head -20
```

You might find patterns like "all good companies have 35-40 employees" → adjust criteria!

### 3. Use Claude Code for Iteration

```bash
claude-code
> Try different employee counts (30, 35, 40) and show me which gives 30 qualified leads
```

Let AI figure out the optimal criteria!

### 4. Batch Process

Have multiple CSVs? Process them all:

```bash
for file in data/raw_*.csv; do
    python scripts/lead_qualifier.py --input "$file" --target 30
done
```

---

## 🆘 Troubleshooting

### "ModuleNotFoundError: No module named 'pandas'"

```bash
pip install -r requirements-file.txt
```

### "FileNotFoundError: data/raw_leads.csv"

Check your file path:
```bash
ls data/  # See what CSV files you have
```

Then use the correct filename:
```bash
python scripts/lead_qualifier.py --input data/YOUR_ACTUAL_FILE.csv --target 30
```

### "Only got 5 leads but need 30"

Your source CSV doesn't have enough qualified companies.

**Fix:**
1. Expand criteria: `--max-employees 40`
2. Get more raw leads from Google Maps
3. Expand to nearby cities

**Claude Code can help:**
```bash
> Help me get 30 qualified leads. I only have 5 right now.
```

### Script runs but no output

Check if the output file was created:
```bash
ls -lh data/qualified_leads*.csv
```

Look for recent files with today's timestamp.

---

## 📈 What's Next?

Once you have qualified leads:

### Phase 2: Research
```bash
# Research your top prospects
python scripts/generate_research.py
```

### Phase 3: Email Generation
```bash
# Generate personalized emails
python scripts/email_generator.py
```

### Phase 4: Outreach
```bash
# Test first
python scripts/email_sender.py --dry-run

# Then send
python scripts/email_sender.py
```

---

## ✅ Success Checklist

After your first run, you should have:

- [ ] Qualified leads CSV with exactly 30 companies
- [ ] All companies have < 30 employees
- [ ] All have valid websites and phone numbers
- [ ] Revenue estimates calculated
- [ ] Excluded leads CSV showing rejection reasons
- [ ] Ready to continue with your email workflow

---

## 🎉 You're Ready!

Run this command right now:

```bash
python scripts/lead_qualifier.py \
    --input data/YOUR_CSV.csv \
    --target 30 \
    --output data/qualified_leads.csv
```

Or with Claude Code:

```bash
claude-code
> Qualify 30 leads from my Hamilton CSV
```

**That's it!** You'll have 30 qualified leads ready for outreach. 🚀

---

## 📞 Need Help?

- **Stuck?** Ask Claude Code: "Help me troubleshoot the lead qualifier"
- **Want customization?** Tell Claude Code what you need
- **Integration issues?** Check CLAUDE_CODE_SETUP.md for details

The system is designed to be simple. If it feels complicated, ask Claude Code to help! 😊
