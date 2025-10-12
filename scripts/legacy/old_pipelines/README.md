# Legacy Pipeline Components

**Status**: ARCHIVED - These components are no longer used in production

## Overview

This directory contains deprecated pipeline implementations that were replaced by the evidence-based validation system (October 2025).

## Archived Components

### 1. RAG Validation System
- **File**: `rag_validator.py`
- **Purpose**: RAG-based lead validation with knowledge base
- **Deprecated**: Replaced by strict gate-based validation
- **Reason**: New system uses explicit gates (category, revenue, geo) instead of RAG inference

### 2. Local LLM Generator
- **File**: `local_llm_generator.py`
- **Purpose**: Local LLM for lead generation and scoring
- **Deprecated**: Replaced by evidence-based generator with strict gates
- **Reason**: LLM approach was too subjective; gates provide deterministic validation

### 3. Lead Generation Pipeline (Old)
- **File**: `lead_generation_pipeline.py`
- **Purpose**: Complete pipeline with sample data generation
- **Deprecated**: Sample data generation disabled, pipeline redesigned
- **Reason**: Violates "no fake data" policy; replaced with real-time external sources

### 4. Auto Feed System
- **File**: `auto_feed.py`
- **Purpose**: Automated feed using RAG + LLM validation
- **Deprecated**: Depends on deprecated RAG/LLM components
- **Reason**: New system uses evidence-based generator with strict gates

### 5. Old Generation Scripts
- **Files**:
  - `generate_comprehensive_leads.py`
  - `generate_multi_source_leads.py`
  - `enrich_leads.py`
  - `enrich_with_apis.py`
- **Purpose**: Various lead generation approaches
- **Deprecated**: Multiple conflicting approaches consolidated
- **Reason**: Replaced by single evidence-based generator (`evidence_based_generator.py`)

## Current Production System

The active production system (October 2025) uses:

### Core Pipeline
- **Main Script**: `generate_v2` → `src/pipeline/evidence_based_generator.py`
- **Gates**: Category, Revenue, Geo gates (`src/gates/`)
- **Website Age**: Wayback Machine service (`src/services/wayback_service.py`)
- **Data Sources**: OpenStreetMap, Yellow Pages, Canadian Importers
- **Validation**: Evidence-based with fingerprinting and observation tracking

### Key Features
1. **Strict Gates**: Deterministic validation (no LLM inference)
2. **Evidence Tracking**: Multi-source corroboration with confidence scores
3. **Real Data Only**: No sample/fake data generation
4. **HITL Review**: Manual review queue for borderline cases
5. **Observability**: Metrics dashboard and comprehensive logging

## Migration Notes

If you need to reference old behavior:

1. **Sample Data**: No longer allowed. Use `BusinessDataAggregator` for real sources
2. **RAG Validation**: Replaced by explicit gate checks with clear pass/fail criteria
3. **LLM Enrichment**: Replaced by API-based enrichment with confidence thresholds
4. **Pipeline Execution**: Use `./generate_v2 <count> --show` instead of old scripts

## Why These Were Deprecated

### Issues with Old System
1. **Sample Data**: Violated "real data only" policy
2. **LLM Validation**: Too subjective, hard to debug, inconsistent results
3. **RAG System**: Overly complex, hard to maintain, unclear failure modes
4. **Multiple Scripts**: Confusion about which script to use
5. **No Clear Gates**: Difficult to understand why leads passed/failed

### Benefits of New System
1. **Deterministic**: Clear gate logic, reproducible results
2. **Transparent**: Know exactly why each lead passed/failed
3. **Testable**: Explicit acceptance tests for all criteria
4. **Maintainable**: Single pipeline with clear stages
5. **Observable**: Comprehensive metrics and logging

## References

- **Deployment Verification**: `/DEPLOYMENT_VERIFICATION.md`
- **Current Implementation**: `/src/pipeline/evidence_based_generator.py`
- **Gate Implementations**: `/src/gates/`
- **Test Suite**: `/tests/test_acceptance_simple.py`

---

**Last Updated**: October 12, 2025
**Status**: Production system validated and deployed
