# Historical Database Files

This folder contains archived database files from the lead generation pipeline development (Oct-Nov 2025).

## Database Files

### leads.db (88KB)
- **Created:** October 11, 2025
- **Purpose:** Original leads database (v1)
- **Status:** Superseded by leads_v2.db

### leads_v2.db (428KB)
- **Created:** October 30, 2025
- **Purpose:** Evidence-based lead generation system
- **Features:** Fingerprinting, observations, validation gates
- **Status:** Superseded by leads_v3.db

### leads_v3.db (432KB)
- **Created:** October 17, 2025
- **Purpose:** Smart discovery pipeline with multi-source aggregation
- **Features:** Source performance tracking, contact enrichment, business type classification
- **Status:** Production version (archived after filter implementation)

### leads_v3.db.backup (0 bytes)
- **Created:** October 13, 2025
- **Purpose:** Empty backup file
- **Status:** Unused

## Current Database

The current active database is not stored in this folder. New lead generation uses:
- **In-memory processing** - No persistent database for filter pipeline
- **CSV exports** - Direct output to `data/outputs/`
- **Filter system** - Processes leads in real-time without database

## Why Archived

These databases represented the **database-first approach** to lead generation:
1. Discover → Store in DB
2. Enrich → Update DB records
3. Validate → Mark DB status
4. Export → Query DB for qualified leads

**New approach (Nov 2025):**
1. Discover → Process immediately
2. Filter → Real-time exclusion
3. Warn → Flag edge cases
4. Export → Direct CSV output

This eliminated database complexity while maintaining data quality through comprehensive filters and test coverage.

## Schema Notes

If you need to inspect these databases:
```bash
sqlite3 leads_v3.db
.schema
SELECT COUNT(*) FROM businesses;
```

Common tables:
- `businesses` - Core business records
- `observations` - Evidence tracking (v2+)
- `validation_results` - Gate results (v2+)
- `source_metrics` - Source performance (v3)

---

**Archived:** November 16, 2025
**Size:** ~1MB total
**Status:** Historical reference only
