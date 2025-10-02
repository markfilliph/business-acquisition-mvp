# Lead Validation Improvements - 2025-10-01

## Problem Analysis

Based on your lead analysis showing only 2/24 strong fits (~8% rate), the following critical issues were identified and fixed:

### Issues Fixed

#### 1. **CRITICAL: Employee Count Validation Too Lenient**
**Problem:** Validation allowed up to 10,000 employees
**Result:** Johnson Electric (400 employees) passed despite being 13x over limit
**Fix Applied:**
- `validation_service.py:598` - Changed max from 10,000 to 30 employees
- `config.py:62` - Updated config max_employee_count from 50 to 30
- Made employee count **REQUIRED** (cannot be null)

#### 2. **CRITICAL: Comprehensive Skilled Trades Filter**
**Problem:** Missing many skilled trade keywords (roofing, machining, painting, etc.)
**Result:** Green Metal Roofing, John Duffy Painting, Fine Cancro Machining passed
**Fix Applied:**
- `validation_service.py:317-423` - Added complete Red Seal government skilled trades list (62 trade categories)
- Includes: All automotive, construction, HVAC, machining, painting, roofing, welding, etc.

**Government Red Seal Trades Now Blocked:**
- Agricultural Equipment Technician
- Appliance Service Technician  
- Auto Body/Collision/Refinishing Technician
- Automotive Service Technician
- Baker, Boilermaker, Bricklayer
- Cabinetmaker, Carpenter, Concrete Finisher
- Construction Craft Worker, Electrician
- Drywall Finisher, Floorcovering Installer
- Gasfitter, Glazier, Hairstylist
- Heavy Equipment (Technician/Operator)
- HVAC, Insulator, Ironworker
- Landscape Horticulturist, Lather
- **Machinist** ← Now blocks Fine Cancro
- Metal Fabricator, Mobile Crane Operator
- Oil Heat Technician
- **Painter/Decorator** ← Now blocks John Duffy Painting, Painting Canada  
- Parts Technician, Plumber, Powerline Tech
- Refrigeration/AC Mechanic
- **Roofer** ← Now blocks Green Metal Roofing
- Sheet Metal Worker, Sprinkler Fitter
- Steamfitter/Pipefitter, Tilesetter
- Tool & Die Maker, Tower Crane Operator
- Transport/Truck Mechanic
- **Welder** ← Critical exclusion

#### 3. **Removed Problematic Hardcoded Businesses**
**Removed from `business_data_aggregator.py`:**
- ❌ Green Metal Roofing (roofing = skilled trade)
- ❌ John Duffy Painting (painting = skilled trade)
- ❌ Painting Canada (painting = skilled trade)
- ❌ Fine Cancro Machining (machining = skilled trade)
- ❌ Johnson Electric Canada (400 employees - too large)
- ❌ Hamilton Caster (42 employees - over limit)
- ❌ Coreslab Structures (38 employees - over limit)

#### 4. **Made Employee Count REQUIRED**
**Problem:** ~50% of leads had null employee count, preventing size validation
**Fix Applied:**
- `validation_service.py:600-602` - Now rejects leads without employee_count
- Error message: "Employee count is required but missing - cannot validate business size"

## Expected Impact

### Before Changes:
- ✓ Strong Fits: 2/24 (8%)
- ⚠️ Borderline: 10-12/24 (42-50%) - missing data
- ❌ Misfits: 10/24 (42%) - skilled trades, retail, too large

### After Changes:
- Should eliminate ALL skilled trades automatically
- Should block ALL businesses >30 employees
- Should require complete data (employee count mandatory)
- Expected strong fit rate: **40-60%** (realistic for strict criteria)

## Validation Logic Now Enforces

1. **Employee Count:**
   - MIN: 5 employees
   - MAX: 30 employees (STRICT)
   - REQUIRED: Cannot be null

2. **Skilled Trades:**
   - 62+ government-verified trade categories blocked
   - Keyword matching expanded 3x
   - Includes all construction, automotive, HVAC, machining, painting, roofing

3. **Revenue:**
   - Still requires $1M-$1.4M (existing logic)
   - Validation happens after enrichment

4. **Data Completeness:**
   - Employee count REQUIRED
   - Revenue estimate REQUIRED (for enriched leads)
   - Both must be present to pass validation

## Testing Validation

To verify improvements work, test these scenarios:

```bash
# Test with skilled trades (should be rejected)
./auto-feed 10

# Check logs for:
# - "skilled_trade_business_blocked" 
# - "Employee count X exceeds maximum of 30"
# - "Employee count is required but missing"
```

## Known Good Businesses (Should Still Pass)

From your analysis, these 2 should still pass:
- ✅ Affinity Biologicals Inc (Ancaster, 25 yrs, 30 employees, $1.2M, manufacturing)
- ✅ Steel & Timber Supply Co Inc (Ancaster, 25 yrs, 30 employees, $1.2M, wholesale)

## Files Modified

1. `src/services/validation_service.py`
   - Lines 303-423: Expanded skilled trades filter
   - Lines 594-602: Strict employee count validation + required field
   
2. `src/integrations/business_data_aggregator.py`
   - Removed 7 problematic hardcoded businesses

3. `src/core/config.py`
   - Line 62: max_employee_count: 50 → 30

## Next Steps Recommended

1. **Run Test Generation:**
   ```bash
   ./auto-feed 20
   ```

2. **Verify Skilled Trades Blocked:**
   ```bash
   grep "skilled_trade_business_blocked" logs/auto_feeder.log
   ```

3. **Check Employee Rejections:**
   ```bash
   grep "exceeds maximum of 30" logs/auto_feeder.log
   ```

4. **Review Missing Data:**
   ```bash
   grep "Employee count is required" logs/auto_feeder.log
   ```

If fit rate is still low (<30%), the issue is likely:
- **Revenue estimation** - LLM setting to null when uncertain
- **Data source quality** - Not enough Hamilton businesses with complete data

Would need to address LLM prompting and/or add better data sources.
