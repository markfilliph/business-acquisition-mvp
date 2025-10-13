# Source Data Files

This directory contains manually exported CSV files from various business data sources.

## Available Sources

### CME (Canadian Manufacturers & Exporters)

**File**: `cme_members.csv`
**Source**: https://cme-mec.ca/find-a-member/
**How to export**:
1. Visit CME member directory
2. Filter: Province = Ontario, City = Hamilton
3. Export results to CSV
4. Save as `cme_members.csv` in this directory

**Expected columns**:
- Company Name
- Address
- City
- Province
- Postal Code
- Phone
- Website
- Industry

---

### Innovation Canada

**File**: `innovation_canada.csv`
**Source**: https://canadiancapabilities.ic.gc.ca
**How to export**:
1. Visit Canadian Company Capabilities database
2. Search: Location = Ontario/Hamilton, Industry = Manufacturing
3. Export results to CSV
4. Save as `innovation_canada.csv` in this directory

**Expected columns**:
- Company_Name
- Address
- City
- Province
- Postal_Code
- Phone
- Website
- Industry
- NAICS_Code

---

## Usage

Once CSV files are in this directory, they will be automatically detected by the pipeline:

```bash
./generate_v3 50
```

The pipeline will use these sources with the following priorities:
1. Seed list (priority 100) - always first
2. Innovation Canada CSV (priority 85)
3. CME CSV (priority 80)
4. Other sources as fallback

---

## Status

- [x] Seed list (built-in, no CSV needed)
- [ ] CME members CSV (manual export required)
- [ ] Innovation Canada CSV (manual export required)

**Note**: The pipeline works without these CSVs using the built-in seed list (20 manufacturers).
