#!/usr/bin/env python3
"""
RAG Lead Validator Demo
Demonstrates how the RAG system would work without complex dependencies
"""

import json
import csv
from datetime import datetime
from typing import List, Dict, Any

class RAGLeadValidatorDemo:
    """
    Demo version of RAG Lead Validator showing the concept
    without requiring ChromaDB/LangChain installation
    """

    def __init__(self):
        # Simulated knowledge base (in real version, this would be ChromaDB)
        self.knowledge_base = [
            {
                "content": "Hamilton Steel Works - 123 Industrial Ave, Hamilton, ON. Manufacturing company operating since 1995. Revenue approximately $1.8M annually. 45 employees. Single location.",
                "metadata": {"business_name": "Hamilton Steel Works", "source": "verified_data"}
            },
            {
                "content": "Mike's Auto Shop - 456 Main St, Hamilton, ON. Automotive repair since 2001. Family-owned business. Revenue around $1.2M. 12 employees. One location only.",
                "metadata": {"business_name": "Mike's Auto Shop", "source": "city_records"}
            },
            {
                "content": "TechStart Solutions Inc - 789 Innovation Drive, Hamilton, ON. IT consulting firm established 2010. Growing rapidly with $2.1M revenue. 25 employees across 3 locations.",
                "metadata": {"business_name": "TechStart Solutions", "source": "business_directory"}
            }
        ]

    def simulate_embedding_search(self, query: str, top_k: int = 3) -> List[Dict]:
        """
        Simulate vector similarity search
        In real version, this would use ChromaDB with embeddings
        """
        # Simple keyword matching for demo
        query_words = query.lower().split()
        scored_results = []

        for doc in self.knowledge_base:
            content_lower = doc["content"].lower()
            # Simple scoring based on keyword matches
            score = sum(1 for word in query_words if word in content_lower)
            if score > 0:
                scored_results.append({
                    "content": doc["content"],
                    "metadata": doc["metadata"],
                    "score": score
                })

        # Sort by score and return top_k
        scored_results.sort(key=lambda x: x["score"], reverse=True)
        return scored_results[:top_k]

    def simulate_llm_validation(self, lead: Dict, context: str) -> Dict:
        """
        Simulate LLM validation response
        In real version, this would call Ollama/LLM
        """
        business_name = lead.get('business_name', '').lower()

        # Simple rule-based validation for demo
        if any(name in context.lower() for name in [business_name]):
            # Found in knowledge base
            confidence = 0.85
            is_valid = True
            evidence = f"Found business information in verified records"
            recommendation = "accept"
            issues = []
        else:
            # Not found in knowledge base
            confidence = 0.2
            is_valid = False
            evidence = "No matching information found in verified sources"
            recommendation = "reject"
            issues = ["Business not found in verified database"]

        return {
            "is_valid": is_valid,
            "confidence": confidence,
            "evidence": evidence,
            "issues": issues,
            "recommendation": recommendation
        }

    def validate_lead(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a single lead against knowledge base
        """
        print(f"Validating: {lead.get('business_name')}")

        # Create search query
        query = f"""
        {lead.get('business_name')}
        {lead.get('address', '')}
        Hamilton Ontario
        """

        # Search knowledge base
        search_results = self.simulate_embedding_search(query)

        # Build context from search results
        context = "\n\n".join([result["content"] for result in search_results])

        # Get LLM validation
        validation_result = self.simulate_llm_validation(lead, context)

        # Add metadata
        validation_result.update({
            'lead_id': lead.get('business_name', 'unknown'),
            'validated_at': datetime.now().isoformat(),
            'sources_checked': len(search_results),
            'retrieved_context': context[:200] + "..." if len(context) > 200 else context
        })

        return validation_result

    def batch_validate(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate multiple leads and return results
        """
        print(f"\n🔍 Validating {len(leads)} leads against knowledge base...")
        print("=" * 50)

        validation_results = []

        for i, lead in enumerate(leads, 1):
            print(f"\n[{i}/{len(leads)}] ", end="")
            result = self.validate_lead(lead)

            # Combine lead data with validation results
            validated_lead = {**lead, **result}

            # Apply confidence thresholds
            if result['confidence'] >= 0.7:
                validated_lead['status'] = 'approved'
                status_icon = "✅"
            elif result['confidence'] >= 0.5:
                validated_lead['status'] = 'review'
                status_icon = "⚠️"
            else:
                validated_lead['status'] = 'rejected'
                status_icon = "❌"

            print(f"{status_icon} {result['recommendation'].upper()} (confidence: {result['confidence']:.1%})")

            validation_results.append(validated_lead)

        # Calculate summary statistics
        approved = len([r for r in validation_results if r['status'] == 'approved'])
        review = len([r for r in validation_results if r['status'] == 'review'])
        rejected = len([r for r in validation_results if r['status'] == 'rejected'])

        print(f"\n{'=' * 50}")
        print(f"📊 VALIDATION SUMMARY")
        print(f"{'=' * 50}")
        print(f"✅ Approved: {approved} ({approved/len(leads)*100:.1f}%)")
        print(f"⚠️  Needs Review: {review} ({review/len(leads)*100:.1f}%)")
        print(f"❌ Rejected: {rejected} ({rejected/len(leads)*100:.1f}%)")

        return validation_results

def main():
    """Demo the RAG validation system"""

    print("🤖 RAG Lead Validator Demo")
    print("=" * 50)
    print("This demo shows how RAG prevents hallucination by")
    print("grounding validation in real document sources.")
    print()

    # Initialize demo validator
    validator = RAGLeadValidatorDemo()

    # Sample leads to validate
    sample_leads = [
        {
            "business_name": "Hamilton Steel Works",
            "address": "123 Industrial Ave",
            "industry": "Manufacturing",
            "estimated_revenue": 1800000,
            "years_in_business": 29
        },
        {
            "business_name": "Mike's Auto Shop",
            "address": "456 Main St",
            "industry": "Automotive",
            "estimated_revenue": 1200000,
            "years_in_business": 23
        },
        {
            "business_name": "Fake Company Ltd",
            "address": "999 Nonexistent St",
            "industry": "Consulting",
            "estimated_revenue": 1500000,
            "years_in_business": 15
        },
        {
            "business_name": "TechStart Solutions",
            "address": "789 Innovation Drive",
            "industry": "Technology",
            "estimated_revenue": 2100000,
            "years_in_business": 14
        }
    ]

    # Run validation
    results = validator.batch_validate(sample_leads)

    # Show detailed results for approved leads
    approved_leads = [r for r in results if r['status'] == 'approved']
    if approved_leads:
        print(f"\n🎯 APPROVED LEADS ({len(approved_leads)}):")
        print("=" * 50)

        for lead in approved_leads:
            print(f"\n🏢 {lead['business_name']}")
            print(f"   📍 {lead['address']}")
            print(f"   🏭 {lead['industry']}")
            print(f"   💰 ${lead['estimated_revenue']:,}")
            print(f"   📅 {lead['years_in_business']} years")
            print(f"   ⭐ Confidence: {lead['confidence']:.1%}")
            print(f"   📝 Evidence: {lead['evidence']}")

    # Save results
    output_file = f"rag_validation_demo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    # Write CSV file
    if results:
        fieldnames = list(results[0].keys())
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
    print(f"\n💾 Results saved to: {output_file}")

    print(f"\n✨ Demo Complete!")
    print(f"In the full RAG system:")
    print(f"• ChromaDB stores thousands of verified business records")
    print(f"• Embeddings enable semantic similarity search")
    print(f"• Local LLM (Mistral/Llama) validates against retrieved docs")
    print(f"• Prevents hallucination by grounding responses in real data")

if __name__ == "__main__":
    main()