# Pipeline Filter Test Suite

Comprehensive test suite for business lead filtering system.

## Overview

This test suite validates:
- **Size filters** - Revenue and employee caps
- **Business type filters** - Retail and location label detection
- **Warning system** - Non-fatal flags for manual review
- **Integration** - Full pipeline behavior on known leads

## Test Structure

```
tests/
├── __init__.py
├── README.md                           # This file
├── test_pipeline_integration.py        # Integration tests (full pipeline)
└── filters/
    ├── __init__.py
    ├── test_size_filters.py            # Size cap tests
    ├── test_business_type_filters.py   # Retail + location tests
    └── test_warning_generator.py       # Warning system tests
```

## Running Tests

### Run All Tests
```bash
# From project root
python scripts/run_tests.py

# Or with pytest directly
./venv/bin/python -m pytest tests/ -v
```

### Run Specific Test File
```bash
python scripts/run_tests.py tests/filters/test_size_filters.py
```

### Run With Coverage
```bash
python scripts/run_tests.py --coverage

# Coverage report will be in htmlcov/index.html
```

### Run Single Test
```bash
./venv/bin/python -m pytest tests/filters/test_size_filters.py::TestSizeFilters::test_exclude_oversized_revenue_vp_expert -v
```

## Test Cases

### Known Good Leads (Should Pass)
Based on original verdict "Core A-List":

✅ Abarth Machining Inc - Clean, no warnings
✅ Stolk Machine Shop Ltd - Clean, no warnings
✅ All Tool Manufacturing Inc - Clean, no warnings
✅ Millen Manufacturing Inc - Clean, no warnings
✅ North Star Technical Inc - Clean, no warnings
✅ G.S. Dunn Ltd - Clean, no warnings (but manual review will catch size)

### Known Bad Leads (Should Exclude)
Based on original verdict "Exclude":

❌ Container57 - Retail (Shopify)
❌ Emerald Manufacturing Site - Location label
❌ VP Expert Machining - Revenue $2.0M > $1.5M cap
❌ Welsh Industrial - Revenue $2.0M > $1.5M cap
❌ Stoney Creek Machine - Revenue $1.9M > $1.5M cap

### Warning Cases (Pass with Flags)
Based on original verdict "Review":

⚠️ Karma Candy Inc - 3 warnings (HIGH_VISIBILITY, UPPER_RANGE, VERIFY_SIZE)
⚠️ Ontario Ravioli - 3 warnings (HIGH_VISIBILITY, UPPER_RANGE, VERIFY_SIZE)
⚠️ Advantage Machining - 1 warning (UPPER_RANGE)
⚠️ Felton Brushes - 1 warning (UPPER_RANGE)

## Test Coverage Goals

Target: **95%+ coverage** for filter logic

- `src/filters/size_filters.py` - 100%
- `src/filters/business_type_filters.py` - 100%
- `src/enrichment/warning_generator.py` - 95%+

## Adding New Tests

### For New Filters
```python
# tests/filters/test_new_filter.py
import pytest
from src.filters.new_filter import NewFilter

class TestNewFilter:
    def test_filter_logic(self):
        """Test description."""
        filter = NewFilter()
        result = filter.apply(test_data)
        assert result == expected
```

### For Known Leads
When adding new test leads from your pipeline:

1. Add to appropriate class in `test_pipeline_integration.py`
2. Use actual data from CSV
3. Document expected behavior (pass/exclude/warn)
4. Run tests to validate

## Expected Results

When running on the current 20-lead pipeline:

```
Total Tests:        60+
Expected to Pass:   60+
Expected Failures:  0
Test Duration:      <5 seconds
```

### Filter Performance Targets

| Filter Type | Precision | Recall | Accuracy |
|-------------|-----------|--------|----------|
| Size | 100% | 50%* | 75% |
| Retail | 100% | 100% | 100% |
| Location Label | 100% | 100% | 100% |
| Warnings | 95%+ | 92%+ | 92%+ |

\* *Recall limited by Google Places data quality (location-specific employee counts)*

## Continuous Integration

To integrate with CI/CD:

```yaml
# .github/workflows/test.yml
name: Test Pipeline Filters

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.12
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: Run tests
        run: python scripts/run_tests.py --coverage
```

## Debugging Failed Tests

### Verbose Output
```bash
./venv/bin/python -m pytest tests/ -vv
```

### Show Print Statements
```bash
./venv/bin/python -m pytest tests/ -s
```

### Stop on First Failure
```bash
./venv/bin/python -m pytest tests/ -x
```

### Show Full Traceback
```bash
./venv/bin/python -m pytest tests/ --tb=long
```

## Maintenance

### When to Update Tests

1. **Config changes** - If TARGET_REVENUE_MAX or MAX_EMPLOYEE_COUNT changes, update expected results
2. **New filters** - Add new test file for new filter logic
3. **Bug fixes** - Add regression test for each bug found
4. **New leads** - Add integration test cases for new pipeline batches

### Test Data Management

Test fixtures are based on real pipeline data. When pipeline changes:

1. Review `test_pipeline_integration.py`
2. Update lead data if source data changed
3. Re-validate expected exclusions/warnings
4. Document changes in commit message

## Troubleshooting

### Import Errors
```bash
# Ensure PYTHONPATH includes src
export PYTHONPATH=/path/to/project:$PYTHONPATH
./venv/bin/python -m pytest tests/
```

### Missing Dependencies
```bash
./venv/bin/pip install pytest pytest-cov
```

### Pydantic Validation Errors
Check that test data includes all required fields for BusinessLead model.

## Performance

Test suite should run in **<5 seconds** on standard hardware.

If tests are slow:
- Check for expensive operations in test fixtures
- Use mocks for external API calls
- Reduce test data size

## Questions?

See:
- Main implementation plan: `docs/PRACTICAL_IMPLEMENTATION_PLAN.md`
- Filter comparison report: `data/outputs/FILTER_VERDICT_COMPARISON_REPORT.md`
- Source code: `src/filters/`, `src/enrichment/`
