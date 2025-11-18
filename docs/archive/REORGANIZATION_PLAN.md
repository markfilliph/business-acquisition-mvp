# File Structure Reorganization Plan

**Date**: October 12, 2025
**Goal**: Clean, logical file organization for production v2 system

---

## Current Issues

### 1. Root Directory Clutter (18 markdown files!)
- Too many documentation files in root
- Implementation notes mixed with user docs
- Makes it hard to find key files

### 2. Confusing Directories
- `cli/` - Nearly empty (just `__init__.py`)
- `models/` - Separate from `src/models/`
- `tools/` - Old tooling
- `chroma_db/` - From deprecated RAG system
- `cache/` - Should be in `data/`
- `dashboard/` - Unclear purpose

### 3. Old Scripts in Root
- `auto-feed` - Deprecated (used old auto_feed.py)
- `quickstart` - May be outdated
- `quickstart.sh` - Duplicate of above?

### 4. Multiple Output Directories
- `output/` - Old outputs
- `exports/` - New exports
- `reports/` - Reports
- Consolidate?

---

## Proposed New Structure

```
business-acquisition-mvp-v2/
├── 📜 README.md                    # Main user documentation
├── 📜 PRODUCTION_DEPLOYMENT.md     # Deployment guide
├── ⚙️  .env                         # Configuration
├── 🚀 generate_v2                  # PRODUCTION COMMAND
│
├── 📂 src/                         # Source code (unchanged - working well)
│   ├── core/                       # Core models, config
│   ├── gates/                      # Validation gates ✅
│   ├── services/                   # Business logic
│   ├── pipeline/                   # Pipeline (evidence_based_generator)
│   ├── integrations/               # External APIs
│   ├── database/                   # Database layer
│   ├── utils/                      # Utilities
│   ├── validation/                 # Validators
│   └── sources/                    # Data sources
│
├── 📂 scripts/                     # Operational scripts
│   ├── review_queue.py             # HITL review ✅
│   ├── metrics_dashboard.py        # Observability ✅
│   ├── build_type_mappings.py      # Utility
│   ├── expand_type_mappings.py     # Utility
│   ├── revalidate_old_leads.py     # Maintenance
│   └── legacy/                     # Archived components
│       └── old_pipelines/          # Deprecated pipelines
│
├── 📂 tests/                       # Test suite
│   ├── test_*_gate.py              # Gate tests ✅
│   ├── test_acceptance_simple.py   # Acceptance tests ✅
│   ├── integration/                # Integration tests
│   └── unit/                       # Unit tests
│
├── 📂 data/                        # All data files
│   ├── leads_v2.db                 # Main database ✅
│   ├── api_cache.db                # API response cache ✅
│   ├── hamilton_postal_codes.json  # Reference data
│   ├── industry_benchmarks.json    # Reference data
│   ├── metrics/                    # Metrics data
│   └── outputs/                    # Generated outputs (NEW)
│       ├── exports/                # CSV/JSON exports
│       ├── reports/                # Summary reports
│       └── logs/                   # Log files
│
├── 📂 docs/                        # All documentation
│   ├── deployment/                 # Deployment docs (NEW)
│   │   ├── COMPONENT_STATUS.md
│   │   ├── DEPLOYMENT_VERIFICATION.md
│   │   ├── DEPLOYMENT_CHECKLIST.md
│   │   └── DEPLOYMENT_STATUS_UPDATE.md
│   ├── implementation/             # Implementation notes (NEW)
│   │   ├── IMPLEMENTATION_PLAN.md
│   │   ├── IMPLEMENTATION_PLAN_UPDATES.md
│   │   ├── PHASE1_COMPLETION.md
│   │   ├── REORGANIZATION_COMPLETE.md
│   │   └── claude_code_implementation.md
│   ├── research/                   # Research docs (NEW)
│   │   ├── DATA_SOURCE_ANALYSIS.md
│   │   ├── CANADIAN_B2B_DATA_SOURCES_RESEARCH.md
│   │   ├── NEW_DATA_SOURCES_IMPLEMENTATION.md
│   │   ├── BUSINESS_TYPE_CLASSIFIER_IMPLEMENTATION.md
│   │   └── 3_SOURCE_IMPLEMENTATION_COMPLETE.md
│   ├── ideas/                      # Planning docs (NEW)
│   │   └── Automated Outreach ideas.md
│   ├── guides/                     # User guides (existing)
│   ├── api/                        # API docs (existing)
│   └── archive/                    # Old docs (existing)
│
├── 📂 config/                      # Configuration files
│   ├── .env.example
│   └── pyproject.toml              # Move here?
│
├── 📂 migrations/                  # Database migrations
│
└── 📂 venv/                        # Virtual environment
```

---

## Reorganization Tasks

### Phase 1: Documentation Cleanup

**Move to `docs/deployment/`:**
- COMPONENT_STATUS.md
- DEPLOYMENT_VERIFICATION.md
- DEPLOYMENT_CHECKLIST.md
- DEPLOYMENT_STATUS_UPDATE.md

**Move to `docs/implementation/`:**
- IMPLEMENTATION_PLAN.md
- IMPLEMENTATION_PLAN_UPDATES.md
- PHASE1_COMPLETION.md
- REORGANIZATION_COMPLETE.md
- claude_code_implementation.md

**Move to `docs/research/`:**
- DATA_SOURCE_ANALYSIS.md
- CANADIAN_B2B_DATA_SOURCES_RESEARCH.md
- NEW_DATA_SOURCES_IMPLEMENTATION.md
- BUSINESS_TYPE_CLASSIFIER_IMPLEMENTATION.md
- 3_SOURCE_IMPLEMENTATION_COMPLETE.md

**Move to `docs/ideas/`:**
- "Automated Outreach ideas.md"

**Keep in Root:**
- README.md (main entry point)
- PRODUCTION_DEPLOYMENT.md (quick reference)
- README_COMMANDS.md (quick reference)

### Phase 2: Clean Up Old Scripts

**Archive to `scripts/legacy/`:**
- `auto-feed` (uses deprecated auto_feed.py)
- `quickstart` (if outdated)
- `quickstart.sh` (if duplicate)

**Keep in Root:**
- `generate_v2` (PRODUCTION COMMAND)

### Phase 3: Directory Consolidation

**Remove/Archive Empty or Deprecated:**
- `cli/` → Archive (only has `__init__.py`)
- `chroma_db/` → Delete (from deprecated RAG system)
- `tools/` → Review and archive if old

**Consolidate Outputs:**
- Move `output/` → `data/outputs/exports/`
- Move `exports/` → `data/outputs/exports/`
- Move `reports/` → `data/outputs/reports/`
- Move `logs/` → `data/outputs/logs/`
- Move `cache/` → `data/cache/` (or delete if old)

**Clean Up:**
- `dashboard/` → Review contents, archive if old
- `templates/` → Keep if used, else archive
- `models/` (root) → Archive (duplicate of src/models/)

### Phase 4: Update References

**Files to update:**
- `.env.example` - Update paths
- `pyproject.toml` - Update paths if needed
- `generate_v2` - Update path if affected
- Any scripts referencing moved files

---

## Benefits

### 1. Clean Root Directory
- Only essential files visible
- Easy to find production command
- Clear entry points (README, PRODUCTION_DEPLOYMENT)

### 2. Organized Documentation
- Implementation notes separate from user docs
- Research separate from deployment docs
- Easy to find what you need

### 3. Consolidated Outputs
- All data in `data/`
- All outputs in `data/outputs/`
- Logical grouping

### 4. Clear Purpose
- Every directory has clear purpose
- No confusion about where files go
- Easy onboarding for new developers

---

## Risk Mitigation

### Before Making Changes:
1. ✅ Git commit current state
2. ✅ Run tests to establish baseline
3. ✅ Document all moves

### During Changes:
1. Use `git mv` for all moves (preserves history)
2. Update imports immediately after each move
3. Test after each phase

### After Changes:
1. Run full test suite
2. Verify `generate_v2` still works
3. Update documentation

---

## Execution Order

1. **Phase 1**: Documentation (low risk, no code changes)
2. **Phase 2**: Old scripts (low risk, deprecated)
3. **Phase 3**: Directory consolidation (medium risk)
4. **Phase 4**: Update references (test after each)

---

## Success Criteria

- ✅ Root has <5 files (README, PRODUCTION_DEPLOYMENT, generate_v2, .env, pyproject.toml)
- ✅ All docs organized in docs/ subdirectories
- ✅ All outputs in data/outputs/
- ✅ 98/98 tests still passing
- ✅ `generate_v2` works without changes
- ✅ No broken imports

---

**Status**: Plan ready for execution
**Estimated Time**: 30-45 minutes
**Risk Level**: Low-Medium (mostly file moves, few code changes)
