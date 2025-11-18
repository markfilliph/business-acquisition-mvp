# Auto-Generation Feature: Always Get Your Target Lead Count

## Overview

The export script now automatically generates more leads when your database doesn't have enough qualified ones to meet your target. **You ask for 30 qualified leads, you get 30 qualified leads** (or as close as possible).

## How It Works

### Scenario 1: Not Enough Qualified Leads

**You run**:
```bash
./venv/bin/python scripts/export_qualified_leads.py --target 30
```

**What happens**:
```
📊 EXPORTING QUALIFIED LEADS
🎯 Target: 30 qualified leads
💾 Database: data/leads_v3.db
🔄 Auto-generate: Yes

✅ Found 5 qualified leads in database

⚠️  Need 25 more qualified leads to reach target

🔄 Automatically generating 450 raw leads...
   (Estimated to yield 25+ qualified leads)

Running: ./generate_v3 450
This may take a few minutes...

[v3 pipeline runs...]

✅ Lead generation complete
✅ Generated 28 additional qualified leads
   Total now: 33 qualified leads

📤 Exporting to: data/qualified_leads_20251015_203000.csv

✅ SUCCESS! Target met: 33/30 qualified leads exported
📂 File: data/qualified_leads_20251015_203000.csv

🎉 Target achieved! You have 33 qualified leads ready for outreach.
```

### Scenario 2: Enough Qualified Leads Already

**You run**:
```bash
./venv/bin/python scripts/export_qualified_leads.py --target 10
```

**What happens** (if database has 33 qualified):
```
📊 EXPORTING QUALIFIED LEADS
🎯 Target: 10 qualified leads
💾 Database: data/leads_v3.db

✅ Found 33 qualified leads in database
   (Already exceeds target, no generation needed)

📤 Exporting to: data/qualified_leads_20251015_203100.csv

✅ SUCCESS! Target met: 33/10 qualified leads exported

🎉 Target achieved! You have 33 qualified leads ready for outreach.
```

### Scenario 3: Disable Auto-Generation

**You run**:
```bash
./venv/bin/python scripts/export_qualified_leads.py --target 30 --no-generate
```

**What happens**:
```
📊 EXPORTING QUALIFIED LEADS
🎯 Target: 30 qualified leads
💾 Database: data/leads_v3.db
🔄 Auto-generate: No

✅ Found 5 qualified leads in database

⚠️  WARNING: Only 5/30 qualified leads available
   Missing: 25 leads

💡 To auto-generate more leads, run without --no-generate flag

📤 Exporting to: data/qualified_leads_20251015_203200.csv

⚠️  PARTIAL SUCCESS: 5/30 qualified leads exported
   Still need 25 more leads to reach target

📊 You have 5 qualified leads (target was 30).
   Consider:
   • Running again to generate more leads
   • Reviewing REVIEW_REQUIRED businesses
   • Slightly relaxing validation criteria
```

## The Math Behind Auto-Generation

### Why 15x Multiplier?

When you need more leads, the script calculates:

```
shortfall = target - current_qualified
fetch_count = shortfall × 15
```

**Example**: Need 20 more qualified leads → Fetch 20 × 15 = 300 raw leads

**Why 15x?**
1. **Strict validation criteria**: ~10% pass all gates (5-30 employees, $1M-$1.4M revenue, 15+ years)
2. **Duplicates**: Some raw leads already in database
3. **Safety buffer**: Better to fetch too many than too few

### Real-World Example

**Your current criteria**:
- Employee count: 5-30
- Revenue: $1M-$1.4M USD
- Years in business: 15+
- Geographic: Hamilton, ON area
- Industries: Manufacturing, B2B services

**Typical qualification rate**: ~10%
- Out of 100 raw businesses fetched
- ~10 will pass all strict validation gates
- ~70 will be AUTO_EXCLUDED (too large, wrong industry, etc.)
- ~20 will be REVIEW_REQUIRED (missing data)

**Buffer ensures success**:
- Need 30 qualified → Fetch 450 raw
- Even with 7% qualification rate → Get 31.5 qualified
- Accounts for duplicates and edge cases

## Command-Line Options

### Default Behavior (Auto-Generate Enabled)

```bash
# Simplest usage - always tries to meet target
./venv/bin/python scripts/export_qualified_leads.py --target 30
```

**When to use**: Normal workflow, you want 30 qualified leads no matter what.

### Disable Auto-Generation

```bash
# Only export what exists, don't generate more
./venv/bin/python scripts/export_qualified_leads.py --target 30 --no-generate
```

**When to use**:
- Just want to see current state
- Don't want to wait for pipeline
- Testing/debugging
- Already ran generation separately

### Specify Output File

```bash
# Custom output filename
./venv/bin/python scripts/export_qualified_leads.py --target 30 --output data/my_leads.csv
```

**When to use**: Need specific filename for integration with other tools.

### Different Database

```bash
# Use different database file
./venv/bin/python scripts/export_qualified_leads.py --db data/test.db --target 50
```

**When to use**: Testing, multiple environments, or different lead pools.

## Exit Codes & Automation

The script returns exit codes for automation:

**Exit Code 0**: Target met (success)
```bash
./venv/bin/python scripts/export_qualified_leads.py --target 30
echo $?  # Prints: 0
```

**Exit Code 1**: Target not met (failure)
```bash
./venv/bin/python scripts/export_qualified_leads.py --target 30 --no-generate
# (Only 5 qualified available)
echo $?  # Prints: 1
```

### Use in Shell Scripts

```bash
#!/bin/bash
# Only continue if we got enough leads
if ./venv/bin/python scripts/export_qualified_leads.py --target 30; then
    echo "✅ Got 30 leads, starting outreach campaign..."
    python scripts/email_sender.py
else
    echo "❌ Not enough leads, aborting"
    exit 1
fi
```

### Chain Commands

```bash
# Only run CRM update if export succeeds
./venv/bin/python scripts/export_qualified_leads.py --target 30 && \
  python scripts/prospects_tracker.py
```

## Real-World Workflows

### Workflow 1: Daily Lead Generation

```bash
#!/bin/bash
# daily_leads.sh - Run every morning

echo "Generating today's leads..."

# Get 30 fresh qualified leads
./venv/bin/python scripts/export_qualified_leads.py \
    --target 30 \
    --output data/leads_$(date +%Y%m%d).csv

if [ $? -eq 0 ]; then
    echo "✅ Success! 30 leads ready for outreach."

    # Update CRM
    python scripts/prospects_tracker.py

    # Send notification
    echo "30 new leads generated" | mail -s "Daily Leads Ready" you@example.com
else
    echo "❌ Failed to generate 30 leads. Check logs."
fi
```

### Workflow 2: On-Demand Batch Generation

```bash
# Generate a large batch for weekly campaign
./venv/bin/python scripts/export_qualified_leads.py --target 100

# The script will:
# 1. Check database (e.g., has 10 qualified)
# 2. Calculate shortfall (need 90 more)
# 3. Run ./generate_v3 1350  (90 × 15)
# 4. Wait for pipeline to finish
# 5. Export all 100+ qualified leads
```

### Workflow 3: Test Without Generation

```bash
# Quick check of current state
./venv/bin/python scripts/export_qualified_leads.py \
    --target 30 \
    --no-generate \
    --output data/current_state.csv

# Review what you have
cat data/current_state.csv | grep QUALIFIED | wc -l
```

### Workflow 4: Continuous Until Target Met

```bash
#!/bin/bash
# keep_trying.sh - Run until we get 30 leads

MAX_ATTEMPTS=5
ATTEMPT=1

while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
    echo "Attempt $ATTEMPT/$MAX_ATTEMPTS"

    if ./venv/bin/python scripts/export_qualified_leads.py --target 30; then
        echo "✅ Success on attempt $ATTEMPT"
        exit 0
    fi

    echo "⚠️  Attempt $ATTEMPT failed, trying again..."
    ATTEMPT=$((ATTEMPT + 1))
    sleep 10
done

echo "❌ Failed after $MAX_ATTEMPTS attempts"
exit 1
```

## Performance Considerations

### Generation Time

**Typical timing for ./generate_v3 pipeline**:
- Fetching 100 raw businesses: ~30 seconds
- Fetching 500 raw businesses: ~2-3 minutes
- Fetching 1000 raw businesses: ~5-7 minutes

**Auto-generation timeout**: 10 minutes
- If pipeline takes >10 minutes, auto-generation fails
- Script continues with whatever leads are available
- Returns exit code 1 (target not met)

### Database Growth

Each run adds to the database:
- **Raw leads**: Never deleted, accumulate over time
- **Qualified leads**: Persist across runs
- **Excluded leads**: Stored for analysis

**Database size**:
- 100 businesses: ~50 KB
- 1,000 businesses: ~500 KB
- 10,000 businesses: ~5 MB

**To start fresh**:
```bash
# Backup current database
mv data/leads_v3.db data/leads_v3_backup.db

# Next run creates new database
./venv/bin/python scripts/export_qualified_leads.py --target 30
```

## Troubleshooting

### "Failed to generate more leads automatically"

**Cause**: ./generate_v3 pipeline failed or timed out

**Solutions**:
1. Run pipeline manually: `./generate_v3 30`
2. Check logs for errors
3. Ensure data sources are accessible
4. Verify API keys are configured

### "Only got 10 qualified, need 30"

**Cause**: Qualification rate lower than expected (15x multiplier not enough)

**Solutions**:
1. **Run again**: `./venv/bin/python scripts/export_qualified_leads.py --target 30`
   - Script will fetch more leads to fill shortfall
2. **Relax criteria**: Edit `src/services/new_validation_service.py`
   - Consider 14-15 years → REVIEW_REQUIRED (instead of AUTO_EXCLUDE)
   - Or lower revenue minimum to $750K
3. **Review REVIEW_REQUIRED leads**: Some may be manually qualifiable

### "Auto-generation keeps running but never reaches target"

**Cause**: Validation criteria too strict for available data sources

**Solutions**:
1. **Check exclusion reasons**:
   ```bash
   grep "EXCLUDED" data/validation_report_*.txt | head -20
   ```
2. **Common issues**:
   - All businesses too large (>30 employees) → Increase to 40-50
   - All businesses too new (<15 years) → Lower to 10+ years
   - Revenue range too narrow → Widen to $500K-$2M
3. **Expand sources**:
   - Add Google Places API
   - Add YellowPages scraper
   - Include nearby cities (Burlington, Oakville)

### "Script times out after 10 minutes"

**Cause**: Large fetch_count (e.g., 1500 raw leads) takes >10 minutes

**Solutions**:
1. **Run in two stages**:
   ```bash
   # Stage 1: Generate
   ./generate_v3 500

   # Stage 2: Export (won't timeout, already in DB)
   ./venv/bin/python scripts/export_qualified_leads.py --target 30 --no-generate
   ```

2. **Increase timeout** (edit script):
   ```python
   timeout=1200  # 20 minutes
   ```

## Comparison: Before vs After

### Before (Manual Process)

```bash
# Check database
sqlite3 data/leads_v3.db "SELECT COUNT(*) FROM businesses WHERE status='QUALIFIED';"
# Result: 5

# Not enough, need to generate more
./generate_v3 30

# Check again
sqlite3 data/leads_v3.db "SELECT COUNT(*) FROM businesses WHERE status='QUALIFIED';"
# Result: 8 (only 3 new qualified)

# Still not enough, generate more
./generate_v3 50

# Check again
sqlite3 data/leads_v3.db "SELECT COUNT(*) FROM businesses WHERE status='QUALIFIED';"
# Result: 15

# Still not enough... (repeat until you give up or reach target)

# Finally export
python scripts/export_leads.py
```

**Time**: 30+ minutes of manual iteration
**Success**: Not guaranteed
**User experience**: Frustrating

### After (Auto-Generation)

```bash
# One command, target guaranteed (or best effort)
./venv/bin/python scripts/export_qualified_leads.py --target 30
```

**Time**: 5-10 minutes (automated)
**Success**: High probability (15x multiplier)
**User experience**: Simple and predictable

## Best Practices

### 1. Start with Realistic Targets

```bash
# Good: Achievable with current sources
./venv/bin/python scripts/export_qualified_leads.py --target 30

# Risky: May take very long or fail
./venv/bin/python scripts/export_qualified_leads.py --target 500
```

### 2. Review First Run Results

```bash
# First run - see what criteria yield
./venv/bin/python scripts/export_qualified_leads.py --target 30

# Check exclusion reasons
cat data/validation_report_*.txt | grep "employee_gate" | wc -l
cat data/validation_report_*.txt | grep "revenue_gate" | wc -l

# Adjust criteria if needed, then re-run
```

### 3. Use --no-generate for Testing

```bash
# Test criteria changes without waiting for generation
# (Use existing database)
./venv/bin/python scripts/export_qualified_leads.py --target 10 --no-generate

# If looks good, run with auto-generation
./venv/bin/python scripts/export_qualified_leads.py --target 30
```

### 4. Monitor Database Growth

```bash
# Check database size
ls -lh data/leads_v3.db

# Check total businesses
sqlite3 data/leads_v3.db "SELECT COUNT(*) FROM businesses;"

# If database gets too large (>100 MB), consider starting fresh
```

## Summary

**Key Points**:
- ✅ **Automatic**: Generates more leads when target not met
- ✅ **Smart**: Uses 15x multiplier based on typical qualification rate
- ✅ **Configurable**: Can disable with `--no-generate`
- ✅ **Reliable**: Returns exit codes for automation
- ✅ **Transparent**: Shows progress and explains what it's doing

**Default behavior**: Ask for 30 qualified leads → Get 30 qualified leads (or script tries its best).

**When it works best**:
- Realistic targets (10-100 leads)
- Sufficient data sources configured
- Reasonable validation criteria
- Good network connectivity

**When to disable auto-generation**:
- Just checking current state
- Testing/debugging
- Already ran generation separately
- Want to control timing manually

---

**Next**: Try it yourself!

```bash
./venv/bin/python scripts/export_qualified_leads.py --target 30
```

The script will handle the rest automatically. 🚀
