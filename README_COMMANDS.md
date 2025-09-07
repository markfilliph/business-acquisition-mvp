# Lead Generation Commands

Simple commands for generating leads during the quality adjustment phase.

## 🛡️ Critical Safeguards Active

All lead generation runs include automatic validation to prevent critical errors:

- ❌ **Skilled Trades Exclusion**: Welding, machining, construction automatically disqualified
- 💰 **Revenue Range Enforcement**: Strict $1M-$1.4M compliance, pipeline aborts on violations  
- 🌐 **Website Verification**: All business websites tested and verified working
- 📍 **Location Validation**: Hamilton, Ontario, Canada area ONLY - rejects US/international
- 🏢 **Fake Business Detection**: Automatic exclusion of test/fake companies

## Quick Commands

### Generate Leads
```bash
# Generate default number of leads (10)
./generate

# Generate specific number of leads
./generate 5
./generate 20

# Generate and show results immediately
./generate 5 --show
./generate --show
```

### View Results
```bash
# Show qualified leads from database
source automation_env/bin/activate && python scripts/show_results.py
```

### Test Configuration
```bash
# Run validation checks
source automation_env/bin/activate && python scripts/test_validation.py
```

## Current Settings

- **Target Revenue**: $1,000,000 - $1,400,000
- **Target Industries**: manufacturing, wholesale, professional_services, printing, equipment_rental
- **Minimum Age**: 15+ years
- **Location**: Hamilton, Ontario area only
- **Excluded**: All skilled trades (welding, machining, construction, etc.)

## Examples

```bash
# Generate 5 leads
./generate 5
✅ GENERATION COMPLETE
   Discovered: 5 businesses
   Validated: 5 leads
   Qualified: 1 leads
   Success Rate: 20.0%
   Duration: 3.8 seconds

# Generate and show immediately
./generate 3 --show
🏢 1. 360 Energy Inc
   📍 1480 Sandhill Drive Unit 8B, Ancaster, ON L9G 4V5
   📞 (905) 304-6001
   🌐 https://360energy.net
   💰 Revenue: $1,381,832
   ⭐ Score: 62/100
```

## Validation Safeguards

✅ **All leads are automatically validated for:**
- Website verification (must be working)
- Revenue range compliance ($1M-$1.4M strictly enforced)  
- Industry targeting (no skilled trades)
- Location verification (Hamilton, ON only)
- Business age (15+ years)

❌ **Automatically excluded:**
- Skilled trades (welding, machining, construction)
- Businesses outside Hamilton area
- Revenue outside $1M-$1.4M range
- Non-working websites
- Fake/test businesses