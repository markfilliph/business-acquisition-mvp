# Claude Code Integration Guide

This guide helps you integrate the improved lead generation system with Claude Code for automated workflow execution.

## 📋 Quick Setup

### 1. Install Dependencies

```bash
# Activate your virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Update dependencies
pip install -r requirements-file.txt
```

### 2. Verify File Structure

Your repository should now have:

```
business-acquisition-mvp/
├── scripts/
│   ├── lead_qualifier.py          # ← NEW: Lead qualification system
│   ├── automated_workflow.py      # ← NEW: Complete pipeline
│   ├── prospects_tracker.py       # Existing Google Sheets CRM
│   ├── email_sender.py            # Existing email automation
│   └── ...
├── data/
│   ├── raw_leads.csv              # Your current CSV with excluded leads
│   ├── qualified_leads.csv        # ← NEW: Output from lead_qualifier.py
│   └── ...
├── requirements-file.txt          # ← UPDATED
├── CLAUDE_CODE_SETUP.md           # ← NEW: This file
├── QUICKSTART.md                  # ← NEW: Quick start guide
└── ...
```

## 🚀 Using the Lead Qualifier

### Basic Usage

Process your existing CSV to get exactly 30 qualified leads:

```bash
python scripts/lead_qualifier.py \
    --input data/raw_leads.csv \
    --target 30 \
    --output data/qualified_leads.csv
```

### Custom Criteria

Adjust qualification criteria:

```bash
python scripts/lead_qualifier.py \
    --input data/hamilton_businesses.csv \
    --target 40 \
    --max-employees 50 \
    --min-revenue 500000 \
    --max-revenue 3000000
```

### Understanding the Output

The script creates **two files**:

1. **`qualified_leads.csv`** - Ready for outreach
   - All leads meet your criteria
   - Employee counts validated or estimated
   - Status: QUALIFIED

2. **`qualified_leads_excluded.csv`** - For review
   - Leads that didn't meet criteria
   - Includes exclusion reasons
   - Useful for adjusting criteria

## 🤖 Claude Code Integration

### Method 1: Direct Command Execution

Create a task file for Claude Code:

**File: `tasks/qualify_leads.yaml`**

```yaml
name: qualify_and_generate_leads
description: Process raw leads and generate qualified prospects for outreach

steps:
  - name: qualify_leads
    command: |
      python scripts/lead_qualifier.py \
        --input data/raw_leads.csv \
        --target 30 \
        --output data/qualified_leads.csv
    
  - name: update_crm
    command: python scripts/prospects_tracker.py
    
  - name: summary
    command: |
      echo "✅ Lead qualification complete"
      echo "Next: Review data/qualified_leads.csv"
      echo "Then run email generation workflow"
```

Run with Claude Code:

```bash
claude-code run tasks/qualify_leads.yaml
```

### Method 2: Interactive Workflow (RECOMMENDED)

Use Claude Code interactively to process leads step-by-step:

```bash
# Start Claude Code
claude-code

# Then in Claude Code, use natural language:
> Run the lead qualifier on data/raw_leads.csv to get 30 qualified leads

# Or more specific:
> Process my Hamilton leads CSV and filter for companies with under 30 employees

# Or ask for help:
> I need 30 qualified leads from my CSV. Help me run the qualification script.
```

**Claude Code will automatically:**
- Find the right script to run
- Determine the correct parameters
- Execute the command
- Show you the results

### Method 3: Full Automation Script

Create an end-to-end workflow:

**File: `scripts/full_workflow.sh`**

```bash
#!/bin/bash

echo "🚀 Starting Business Acquisition Workflow"
echo "=========================================="

# Step 1: Qualify leads
echo ""
echo "📊 Step 1: Qualifying leads..."
python scripts/lead_qualifier.py \
    --input data/raw_leads.csv \
    --target 30 \
    --output data/qualified_leads.csv

if [ $? -ne 0 ]; then
    echo "❌ Lead qualification failed"
    exit 1
fi

# Step 2: Update Google Sheets CRM
echo ""
echo "📈 Step 2: Updating CRM..."
python scripts/prospects_tracker.py

# Step 3: Generate research briefs (if you have this)
# echo ""
# echo "🔍 Step 3: Generating research..."
# python scripts/generate_research.py

# Step 4: Summary
echo ""
echo "✅ Workflow complete!"
echo ""
echo "📊 Results:"
wc -l data/qualified_leads.csv
echo ""
echo "🚀 Next steps:"
echo "   1. Review qualified_leads.csv"
echo "   2. Run email generation"
echo "   3. Start outreach campaign"
```

Make it executable:

```bash
chmod +x scripts/full_workflow.sh
```

Run with Claude Code:

```bash
claude-code

> Run the full workflow script
```

Or directly:

```bash
claude-code run scripts/full_workflow.sh
```

## 🔧 Troubleshooting with Claude Code

### Problem: "Not enough qualified leads"

```bash
claude-code

> I only got 15 qualified leads but need 30. Help me analyze the excluded leads and adjust criteria.
```

**Claude Code will:**
1. Read your excluded leads CSV
2. Analyze the exclusion reasons
3. Suggest criteria adjustments
4. Re-run with new parameters
5. Show you the results

### Problem: "Too many leads excluded for employee count"

```bash
claude-code

> Analyze data/qualified_leads_excluded.csv and determine the optimal max employee count to get 30 qualified leads
```

**Claude Code will:**
- Parse the excluded CSV
- Count exclusions by reason
- Calculate optimal thresholds
- Suggest new criteria
- Offer to re-run

### Problem: "Missing employee data"

```bash
claude-code

> Help me estimate employee counts for the REVIEW_REQUIRED leads using their website and industry
```

**Claude Code can:**
- Visit company websites
- Extract team information
- Estimate from industry norms
- Update your CSV
- Re-run qualification

## 📖 Claude Code Task Examples

### Task: Optimize Lead Criteria

```bash
claude-code

> Task: Analyze my excluded leads and find the optimal criteria to get exactly 30 qualified leads from Hamilton, ON. The current criteria are:
> - Max employees: 30
> - Revenue: $250k-$2M
> 
> Input file: data/raw_leads.csv
> Show me what criteria changes would get me to 30 leads.
```

**Claude Code will:**
1. Read the excluded leads CSV
2. Analyze exclusion reasons
3. Calculate statistics (e.g., "22 excluded for 31-40 employees")
4. Suggest: "Increase max_employees to 40"
5. Re-run with optimized settings
6. Show before/after comparison

### Task: Enrich Missing Data

```bash
claude-code

> Task: For all leads with status REVIEW_REQUIRED in data/raw_leads.csv:
> 1. Visit their website
> 2. Estimate employee count from team page or about page
> 3. Update the CSV with estimates
> 4. Re-run qualification
```

**Claude Code will:**
- Parse the CSV
- Find REVIEW_REQUIRED leads
- Visit each website
- Extract employee info
- Update CSV
- Re-qualify

### Task: Expand Search Area

```bash
claude-code

> Task: I need 30 qualified leads but only found 12 in Hamilton. 
> Help me:
> 1. Identify nearby cities (Burlington, Oakville, Stoney Creek)
> 2. Search for businesses in those areas
> 3. Combine with Hamilton leads
> 4. Qualify until I have 30 total
```

**Claude Code will:**
- Research nearby cities
- Fetch additional leads
- Merge datasets
- Run qualification
- Ensure 30 qualified total

### Task: Process Multiple Files

```bash
claude-code

> Process all CSV files in the data/ directory and combine qualified leads into one master file
```

**Claude Code will:**
- List all CSVs in data/
- Process each one
- Deduplicate
- Merge results
- Output master CSV

## 🎯 Integration with Your Existing Workflow

### Before (Original Workflow)

```
1. Fetch leads from Google Maps
2. Get ~27 excluded, ~3 qualified ❌
3. Manually search for more leads
4. Repeat until you have enough
```

### After (Improved Workflow)

```
1. Fetch initial batch → data/raw_leads.csv
2. Run: python scripts/lead_qualifier.py --target 30
3. Get exactly 30 qualified leads ✅
4. Continue with your existing email workflow
```

### Updated Phase 1 Process

**Original Phase 1:**
```bash
# Find businesses (manual or script)
# Result: Mixed qualified/unqualified in one CSV
```

**New Phase 1 with Claude Code:**
```bash
claude-code

> Fetch 100 businesses from Hamilton, qualify them, and give me 30 that meet our criteria
```

**Claude Code handles:**
1. Fetching raw leads
2. Running qualification
3. Ensuring you get exactly 30
4. Updating CRM
5. Showing next steps

**Then continue with existing Phase 2:**
```bash
python scripts/prospects_tracker.py
```

## 💡 Pro Tips for Claude Code

### 1. Use Natural Language Commands

Instead of remembering exact syntax:

```bash
claude-code

# Just describe what you want:
> Get me 30 qualified leads from the raw CSV, max 30 employees, revenue under $2M

# Or ask questions:
> What files do I have in the data directory?

# Or request analysis:
> Why am I only getting 10 qualified leads?
```

Claude Code figures out the commands.

### 2. Chain Multiple Steps

```bash
claude-code

> First qualify leads, then update the CRM, then show me statistics

# Or:
> Process my leads, send me a summary email with results, and prepare the next outreach batch
```

### 3. Debug with Claude Code

```bash
claude-code

> The lead qualifier says I only have 5 qualified leads. Show me why the others were excluded and suggest fixes.
```

**Claude Code will:**
- Open excluded CSV
- Analyze reasons
- Show statistics
- Suggest solutions
- Offer to implement

### 4. Iterate Quickly

```bash
claude-code

> Try max employees of 35 instead of 30
> Now try including Burlington too
> Show me the difference in results
```

Each iteration takes seconds, not manual work.

### 5. Ask for Explanations

```bash
claude-code

> Explain what the lead qualifier script does and show me an example run

# Or:
> What's the difference between qualified_leads.csv and qualified_leads_excluded.csv?
```

## 🔄 Continuous Improvement Loop

Use this workflow to continuously improve your lead quality:

**With Claude Code:**

```bash
claude-code

> Help me optimize my lead criteria. Run multiple tests with different employee limits (25, 30, 35, 40) and show me which gives the best balance of quantity and quality.
```

**Claude Code will:**
1. Run 4 different tests
2. Compare results
3. Show statistics for each
4. Recommend optimal setting
5. Implement the best one

**Manual Script (if you prefer):**

```bash
#!/bin/bash
# continuous_improvement.sh

echo "🔄 Running continuous lead optimization..."

# Try different criteria and track results
for max_emp in 25 30 35 40; do
    echo "Testing max employees: $max_emp"
    
    python scripts/lead_qualifier.py \
        --input data/raw_leads.csv \
        --target 30 \
        --max-employees $max_emp \
        --output "data/test_${max_emp}.csv"
    
    # Count results
    count=$(wc -l < "data/test_${max_emp}.csv")
    echo "Result: $count qualified leads"
done

echo "✅ Optimization complete. Review test_*.csv files"
```

## 📊 Monitoring and Reporting

Ask Claude Code to create reports:

```bash
claude-code

> Create a daily report showing:
> - How many leads were processed today
> - Qualification success rate
> - Top exclusion reasons
> - Recommendations for tomorrow
```

**Claude Code generates:**
- CSV summary
- Text report
- Statistics
- Actionable insights

## 🎬 Real-World Usage Scenarios

### Scenario 1: Quick Daily Run

```bash
claude-code

> Process today's leads and update the CRM
```

Done in one command!

### Scenario 2: Emergency - Need Leads Fast

```bash
claude-code

> I need 30 qualified leads in the next 10 minutes. Hamilton, under 30 employees, revenue $250k-$2M. Go!
```

Claude Code handles it.

### Scenario 3: Quality Check

```bash
claude-code

> Review my qualified leads from yesterday and flag any that might not be a good fit
```

### Scenario 4: Weekly Optimization

```bash
claude-code

> Analyze last week's lead qualification runs. What criteria changes would improve our success rate?
```

### Scenario 5: Data Enrichment

```bash
claude-code

> I have leads missing employee counts. Visit their websites, LinkedIn pages, and estimate the data. Update my CSV.
```

## 🆘 Getting Help from Claude Code

If you're stuck, Claude Code is your debugging assistant:

```bash
claude-code

# General help:
> Help me understand the lead qualification workflow

# Specific errors:
> I'm getting this error: [paste error]. Fix it.

# Performance:
> The script is slow. How can I speed it up?

# Strategy:
> I can't find enough qualified leads. What should I do?
```

**Claude Code can:**
- Debug errors
- Explain concepts
- Suggest improvements
- Implement fixes
- Test solutions

## 📚 Command Reference

### Quick Commands for Claude Code

```bash
# Basic qualification
> Qualify 30 leads from my CSV

# With criteria
> Qualify leads with max 40 employees and revenue under $3M

# Analysis
> Analyze my excluded leads and tell me why

# Optimization
> Find the best criteria to get 30 leads

# Full workflow
> Run the complete workflow from leads to CRM update

# Debugging
> Why did this lead get excluded?

# Reporting
> Show me statistics on my last qualification run

# Batch processing
> Process all CSV files in data/ directory
```

## 🎓 Learning Path

### Week 1: Basic Usage
```bash
claude-code
> Run basic lead qualification on my CSV
```

### Week 2: Optimization
```bash
> Help me optimize criteria for better results
```

### Week 3: Automation
```bash
> Set up automated daily lead processing
```

### Week 4: Advanced
```bash
> Build a complete pipeline from lead fetching to email sending
```

## 📞 Support

For issues with:
- **Lead Qualifier Script**: Check logs in the terminal output
- **Claude Code Integration**: Visit https://docs.claude.com/claude-code
- **Google Sheets**: Check credentials.json configuration
- **General Questions**: Ask Claude Code directly!

## ✅ Verification Checklist

Before running your first campaign:

- [ ] `lead_qualifier.py` is in `scripts/` directory
- [ ] Updated `requirements-file.txt` is installed
- [ ] Test command runs: `python scripts/lead_qualifier.py --help`
- [ ] You have a `data/raw_leads.csv` file
- [ ] You get qualified leads output
- [ ] Qualified leads integrate with `prospects_tracker.py`
- [ ] Claude Code is installed and accessible

## 🎉 Success Metrics

After implementation, you should see:

- ✅ **100% quota fulfillment** - You asked for 30, you get 30
- ✅ **No more manual filtering** - All done automatically
- ✅ **Clear exclusion reasons** - Know exactly why leads don't qualify
- ✅ **Faster iteration** - Test new criteria in seconds with Claude Code
- ✅ **Better targeting** - Only reach out to truly qualified prospects
- ✅ **Time saved** - Hours of manual work → 1 command

## 🚀 Ready to Start?

**Simplest way:**

```bash
claude-code

> I need 30 qualified business leads from Hamilton, ON with under 30 employees and revenue between $250k-$2M. Process my raw leads CSV and give me the results.
```

**That's it!** Claude Code handles everything. 🎯

---

**Pro Tip:** Keep Claude Code open while working on your acquisition campaign. Anytime you need something - data analysis, script runs, debugging, optimization - just ask in natural language!
