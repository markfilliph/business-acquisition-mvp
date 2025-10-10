"""
Anti-hallucination prompts for LLM extraction.
PRIORITY: P0 - Critical for revenue gate accuracy.
"""

WEBSITE_EXTRACTION_SYSTEM_PROMPT = """You are a precise data extraction assistant specializing in manufacturing business information.

CRITICAL RULES (Follow exactly):
1. ONLY extract information that is EXPLICITLY STATED in the content
2. If information is not found, return NULL - NEVER GUESS or INFER
3. Do NOT extrapolate from qualitative descriptions (e.g., "small team" does NOT mean "5 employees")
4. Do NOT infer founding year from domain registration or copyright dates
5. Be skeptical - if confidence is low, set confidence_score < 0.5
6. Extract EXACT numbers only, not ranges or estimates

EXAMPLES OF CORRECT EXTRACTION:
- Text: "Founded in 1987" → founding_year: 1987 ✓
- Text: "Our team of 25 employees" → staff_count: 25 ✓
- Text: "50,000 square foot facility" → facility_sqft: 50000 ✓

EXAMPLES OF INCORRECT EXTRACTION (HALLUCINATION):
- Text: "Small family business" → staff_count: 5 ✗ (NOT stated explicitly)
- Text: "Copyright © 2005" → founding_year: 2005 ✗ (copyright ≠ founding)
- Text: "Large workforce" → staff_count: 100 ✗ (qualitative, not quantitative)
- Text: "Multiple locations" → staff_count: 50 ✗ (NEVER infer from facilities)

YOUR TASK:
Extract the following from the website content:
- founding_year (int): Year founded (MUST be explicitly stated)
- staff_count (int): Number of employees (MUST be explicitly stated)
- facility_sqft (int): Facility size in sq ft (MUST be explicitly stated)
- certifications (list): ISO, AS9100, etc. (only if listed)
- equipment_mentions (list): CNC machines, welding equipment, etc.
- services_offered (list): Specific capabilities mentioned
- confidence_score (float 0-1): Your confidence in extraction quality
- extraction_notes (str): Any caveats or context

When in doubt, leave fields as NULL and explain in extraction_notes.
"""

WEBSITE_EXTRACTION_USER_PROMPT_TEMPLATE = """Extract business information from the following website content:

URL: {url}
Company Name: {company_name}

=== WEBSITE CONTENT ===
{content}
=== END CONTENT ===

Extract the information following the rules in the system prompt.
Return ONLY the JSON object with no additional commentary.
"""


def build_extraction_prompt(url: str, company_name: str, content: str, max_content_length: int = 8000) -> dict:
    """
    Build extraction prompt with content truncation.

    Args:
        url: Website URL
        company_name: Business name
        content: Scraped website content
        max_content_length: Maximum characters to send (token limit protection)

    Returns:
        Dict with 'system' and 'user' messages
    """
    # Truncate content if too long (protect against token limits)
    if len(content) > max_content_length:
        content = content[:max_content_length] + "\n\n[...TRUNCATED...]"

    user_prompt = WEBSITE_EXTRACTION_USER_PROMPT_TEMPLATE.format(
        url=url,
        company_name=company_name,
        content=content
    )

    return {
        'system': WEBSITE_EXTRACTION_SYSTEM_PROMPT,
        'user': user_prompt
    }


# Validation prompt for double-checking suspicious extractions
VALIDATION_PROMPT_TEMPLATE = """You previously extracted the following data from a business website:

{extracted_data}

Review your extraction for potential hallucinations:
1. Was founding_year EXPLICITLY stated, or did you infer it from copyright/domain?
2. Was staff_count EXPLICITLY stated, or did you infer from company size adjectives?
3. Was facility_sqft EXPLICITLY stated as a number?

For each field, respond with:
- VALID: Information was explicitly stated
- SUSPECT: Information may have been inferred
- INVALID: Information was definitely hallucinated

Return JSON with validation results:
{{
    "founding_year_valid": "VALID|SUSPECT|INVALID",
    "staff_count_valid": "VALID|SUSPECT|INVALID",
    "facility_sqft_valid": "VALID|SUSPECT|INVALID",
    "overall_confidence": 0.0-1.0,
    "recommended_action": "ACCEPT|REVIEW|REJECT"
}}
"""


def build_validation_prompt(extracted_data: dict) -> str:
    """Build validation prompt for double-checking extraction."""
    import json
    return VALIDATION_PROMPT_TEMPLATE.format(
        extracted_data=json.dumps(extracted_data, indent=2)
    )
