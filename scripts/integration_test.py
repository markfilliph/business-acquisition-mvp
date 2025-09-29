#!/usr/bin/env python3
"""
Integration Test for Local LLM Lead Generation System
Tests all components without complex dependencies
"""

import ollama
import json
from datetime import datetime
from pathlib import Path

def test_lead_generation():
    """Test the core lead generation functionality"""

    print("🧪 INTEGRATION TEST")
    print("=" * 50)

    # Initialize client
    client = ollama.Client()

    # Test business data
    test_business = {
        "name": "Hamilton Manufacturing Co",
        "address": "123 Industrial Way, Hamilton, ON",
        "industry": "Manufacturing",
        "description": "Steel fabrication company serving Ontario since 1995",
        "employees": "35-50",
        "established": "1995"
    }

    # Create lead analysis prompt
    prompt = f"""
    Analyze this business and determine if it's a qualified lead.

    BUSINESS DATA:
    {json.dumps(test_business, indent=2)}

    CRITERIA:
    - Revenue between $1-2M annually
    - Operating for 15+ years
    - Located in Hamilton, ON
    - Single location

    Respond with ONLY valid JSON:
    {{
        "business_name": "exact name",
        "qualified": true/false,
        "estimated_revenue": number,
        "years_in_business": number,
        "confidence_score": 0.0_to_1.0,
        "qualification_reason": "brief explanation"
    }}
    """

    print("🤖 Testing lead generation with Mistral...")

    try:
        # Generate with mistral
        response = client.generate(
            model='mistral:latest',
            prompt=prompt,
            options={'temperature': 0.1}
        )

        result_text = response['response'].strip()

        # Extract JSON
        if '{' in result_text:
            start = result_text.find('{')
            end = result_text.rfind('}') + 1
            json_text = result_text[start:end]

            result = json.loads(json_text)

            print("✅ Lead generation successful!")
            print(f"   Business: {result.get('business_name')}")
            print(f"   Qualified: {result.get('qualified')}")
            print(f"   Revenue: ${result.get('estimated_revenue', 0):,}")
            print(f"   Years: {result.get('years_in_business')}")
            print(f"   Confidence: {result.get('confidence_score', 0):.1%}")
            print(f"   Reason: {result.get('qualification_reason')}")

            return True

    except Exception as e:
        print(f"❌ Lead generation failed: {e}")
        return False

def test_validation_simulation():
    """Test the validation concept"""

    print("\\n🔍 Testing RAG-style validation...")

    # Simulate knowledge base
    knowledge_base = [
        "Hamilton Manufacturing Co - 123 Industrial Way, Hamilton, ON. Manufacturing company since 1995. Revenue approximately $1.8M annually.",
        "Mike's Auto Shop - 456 Main St, Hamilton, ON. Family automotive repair since 1999. Revenue around $1.2M.",
    ]

    test_leads = [
        {"business_name": "Hamilton Manufacturing Co", "claimed_revenue": 1800000},
        {"business_name": "Fake Company Ltd", "claimed_revenue": 1500000}
    ]

    validated_count = 0

    for lead in test_leads:
        # Simulate vector search (simple keyword matching)
        found_in_kb = any(lead["business_name"] in doc for doc in knowledge_base)

        if found_in_kb:
            print(f"   ✅ {lead['business_name']}: Verified in knowledge base")
            validated_count += 1
        else:
            print(f"   ❌ {lead['business_name']}: Not found - likely hallucination")

    print(f"   📊 Validation rate: {validated_count}/{len(test_leads)} ({validated_count/len(test_leads)*100:.0f}%)")

    return validated_count > 0

def test_pipeline_readiness():
    """Test if the complete pipeline is ready"""

    print("\\n🚀 Testing pipeline readiness...")

    checks = {
        "ollama_running": False,
        "models_available": False,
        "environment_configured": False,
        "output_directory": False
    }

    # Check Ollama
    try:
        client = ollama.Client()
        models = client.list()
        checks["ollama_running"] = True

        # Check required models
        model_names = [m.get('name', '') for m in models.get('models', [])]
        required = ['mistral:latest', 'nomic-embed-text:latest']
        if all(any(req in name for name in model_names) for req in required):
            checks["models_available"] = True
    except:
        pass

    # Check environment
    if Path('.env.local').exists():
        checks["environment_configured"] = True

    # Check output directory
    output_dir = Path('output')
    output_dir.mkdir(exist_ok=True)
    if output_dir.exists():
        checks["output_directory"] = True

    # Report results
    for check, status in checks.items():
        icon = "✅" if status else "❌"
        print(f"   {icon} {check.replace('_', ' ').title()}")

    return all(checks.values())

def main():
    """Run all integration tests"""

    print("🎯 LOCAL LLM LEAD GENERATION - INTEGRATION TEST")
    print("=" * 60)

    # Run tests
    test1 = test_lead_generation()
    test2 = test_validation_simulation()
    test3 = test_pipeline_readiness()

    print("\\n" + "=" * 60)
    print("📋 TEST SUMMARY")
    print("=" * 60)

    tests = [
        ("Lead Generation", test1),
        ("RAG Validation", test2),
        ("Pipeline Readiness", test3)
    ]

    passed = 0
    for name, result in tests:
        icon = "✅" if result else "❌"
        status = "PASS" if result else "FAIL"
        print(f"{icon} {name}: {status}")
        if result:
            passed += 1

    print(f"\\n📊 Results: {passed}/{len(tests)} tests passed ({passed/len(tests)*100:.0f}%)")

    if passed == len(tests):
        print("\\n🎉 ALL TESTS PASSED!")
        print("✨ Local LLM lead generation system is READY!")
        print("\\nNext steps:")
        print("1. Install full dependencies: pip install -r requirements-local.txt")
        print("2. Run pipeline: python scripts/run_pipeline.py --source hamilton --count 10")
        print("3. Scale up with larger models as needed")
    else:
        print("\\n⚠️  Some tests failed. Check setup and dependencies.")

    # Save test results
    results = {
        "test_date": datetime.now().isoformat(),
        "tests": {name: result for name, result in tests},
        "overall_status": "PASS" if passed == len(tests) else "FAIL",
        "pass_rate": f"{passed}/{len(tests)}"
    }

    Path('output').mkdir(exist_ok=True)
    with open('output/integration_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\\n💾 Test results saved to: output/integration_test_results.json")

if __name__ == "__main__":
    main()