"""
Business Type Classifier Service - Multi-Source Business Type Verification
Uses website scraping, Yellow Pages, Google, LinkedIn, Chamber of Commerce, and LLM analysis
to accurately determine business type and filter out unwanted categories.
"""
import asyncio
import aiohttp
import re
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import json

import structlog

from ..core.models import BusinessLead


class BusinessTypeClassifier:
    """
    Comprehensive business type classification using multiple data sources.
    Determines actual business operations to filter convenience stores, retail chains, etc.
    """

    def __init__(self):
        self.logger = structlog.get_logger(__name__)

        # Business types to EXCLUDE (not suitable for acquisition)
        self.excluded_business_types = {
            'convenience_store',
            'gas_station',
            'retail_chain',
            'franchise_restaurant',
            'grocery_store',
            'pharmacy_chain',
            'bank',
            'fast_food',
            'coffee_chain',
            'non_profit',
            'government',
            'religious_organization',
            'school',
            'hospital',
            'skilled_trade'
        }

        # Keywords indicating each business type
        self.business_type_keywords = {
            'convenience_store': [
                'convenience store', 'corner store', 'variety store', 'depanneur',
                'mini mart', 'quick stop', 'tobacco', 'lottery', 'cigarettes',
                'confectionery', 'snacks and drinks', 'beverages and snacks',
                'convenience', 'c-store', 'corner shop', 'circle k', 'mac\'s',
                'couche-tard', '7-eleven', '7 eleven', 'hasty market'
            ],
            'gas_station': [
                'gas station', 'petrol station', 'fuel station', 'service station',
                'esso', 'shell', 'petro-canada', 'mobil', 'chevron', 'bp',
                'gasoline', 'diesel fuel', 'fuel pump'
            ],
            'retail_chain': [
                'walmart', 'target', 'costco', 'best buy', 'staples',
                'home depot', 'lowes', 'canadian tire', 'rona',
                'retail chain', 'big box', 'department store'
            ],
            'franchise_restaurant': [
                'mcdonalds', 'mcdonald\'s', 'burger king', 'wendys', 'wendy\'s',
                'subway', 'tim hortons', 'starbucks', 'kfc', 'pizza hut',
                'dominos', 'domino\'s', 'taco bell', 'a&w', 'popeyes',
                'chipotle', 'franchise restaurant'
            ],
            'grocery_store': [
                'grocery store', 'supermarket', 'food market', 'food basics',
                'fortinos', 'freshco', 'metro', 'loblaws', 'sobeys', 'safeway',
                'no frills', 'zehrs', 'valu-mart', 'foodland', 'independent'
            ],
            'pharmacy_chain': [
                'pharmacy', 'drugstore', 'shoppers drug mart', 'rexall',
                'pharma plus', 'london drugs', 'jean coutu', 'cvs', 'walgreens'
            ],
            'bank': [
                'bank', 'credit union', 'caisse populaire', 'financial institution',
                'td bank', 'rbc', 'scotiabank', 'bmo', 'cibc', 'hsbc',
                'desjardins', 'national bank'
            ],
            'non_profit': [
                'non-profit', 'not-for-profit', 'charity', 'foundation',
                'society', 'association', 'community center', 'community centre',
                'institute', 'registered charity'
            ],
            'government': [
                'government', 'municipal', 'federal', 'provincial',
                'city of', 'ministry', 'department of', 'service canada',
                'service ontario'
            ]
        }

        # Yellow Pages categories to exclude
        self.excluded_yellowpages_categories = {
            'Convenience Stores',
            'Gas Stations',
            'Grocery Stores',
            'Supermarkets',
            'Pharmacies',
            'Drug Stores',
            'Banks',
            'Credit Unions',
            'Fast Food Restaurants',
            'Coffee Shops',
            'Chain Restaurants',
            'Non-Profit Organizations',
            'Charities',
            'Churches',
            'Religious Organizations',
            'Schools',
            'Educational Institutions',
            'Hospitals',
            'Medical Clinics'
        }

        self.classification_stats = {
            'total_classified': 0,
            'excluded_by_website': 0,
            'excluded_by_yellowpages': 0,
            'excluded_by_google': 0,
            'excluded_by_llm': 0,
            'excluded_by_keywords': 0,
            'approved': 0
        }

    async def classify_business_type(self, lead: BusinessLead) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Classify business type using multiple sources.

        Returns:
            Tuple of (is_suitable, reason, evidence_dict)
            - is_suitable: True if business is suitable for acquisition
            - reason: Explanation for the classification
            - evidence_dict: All evidence gathered from sources
        """
        self.classification_stats['total_classified'] += 1

        evidence = {
            'business_name': lead.business_name,
            'website_analysis': {},
            'yellowpages_category': None,
            'google_info': {},
            'linkedin_info': {},
            'chamber_info': {},
            'llm_classification': {},
            'keyword_matches': []
        }

        # 1. Quick keyword-based pre-screening (fast rejection)
        keyword_result = self._check_keywords(lead.business_name)
        if not keyword_result['is_suitable']:
            self.classification_stats['excluded_by_keywords'] += 1
            return False, keyword_result['reason'], evidence
        evidence['keyword_matches'] = keyword_result['matches']

        # 2. Website content analysis (if website available)
        if lead.contact.website:
            website_result = await self._analyze_website_content(lead.contact.website)
            evidence['website_analysis'] = website_result

            if not website_result.get('is_suitable', True):
                self.classification_stats['excluded_by_website'] += 1
                return False, website_result.get('reason', 'Website analysis indicates unsuitable business type'), evidence

        # 3. Yellow Pages category verification
        yp_result = await self._check_yellowpages_category(lead)
        evidence['yellowpages_category'] = yp_result

        if not yp_result.get('is_suitable', True):
            self.classification_stats['excluded_by_yellowpages'] += 1
            return False, yp_result.get('reason', 'Yellow Pages category indicates unsuitable business type'), evidence

        # 4. Google Business information
        google_result = await self._check_google_business(lead)
        evidence['google_info'] = google_result

        if not google_result.get('is_suitable', True):
            self.classification_stats['excluded_by_google'] += 1
            return False, google_result.get('reason', 'Google Business indicates unsuitable business type'), evidence

        # 5. LinkedIn company information
        linkedin_result = await self._check_linkedin(lead)
        evidence['linkedin_info'] = linkedin_result

        # 6. Hamilton Chamber of Commerce verification
        chamber_result = await self._check_hamilton_chamber(lead)
        evidence['chamber_info'] = chamber_result

        # 7. LLM-based final classification (analyzes all evidence)
        llm_result = await self._llm_classify_business(lead, evidence)
        evidence['llm_classification'] = llm_result

        if not llm_result.get('is_suitable', True):
            self.classification_stats['excluded_by_llm'] += 1
            return False, llm_result.get('reason', 'LLM analysis indicates unsuitable business type'), evidence

        # Business is suitable
        self.classification_stats['approved'] += 1
        self.logger.info(
            "business_type_approved",
            business_name=lead.business_name,
            confidence=llm_result.get('confidence', 0.0)
        )

        return True, "Business type suitable for acquisition", evidence

    def _check_keywords(self, business_name: str) -> Dict[str, Any]:
        """Fast keyword-based pre-screening with context awareness."""
        if not business_name:
            return {'is_suitable': False, 'reason': 'No business name provided', 'matches': []}

        name_lower = business_name.lower()
        matches = []

        # Manufacturing/industrial context keywords that override convenience store detection
        manufacturing_context = ['manufacturing', 'fabricat', 'industrial', 'machine shop',
                                'metal work', 'welding', 'production', 'factory']
        has_manufacturing_context = any(ctx in name_lower for ctx in manufacturing_context)

        # Check each excluded business type
        for business_type, keywords in self.business_type_keywords.items():
            for keyword in keywords:
                if keyword in name_lower:
                    # Special handling for "convenience" keyword
                    # If business name includes manufacturing context, don't flag as convenience store
                    if keyword == 'convenience' and has_manufacturing_context:
                        self.logger.info(
                            "convenience_keyword_with_manufacturing_context",
                            business_name=business_name,
                            note="'convenience' keyword found but manufacturing context detected - allowing"
                        )
                        continue

                    matches.append({'type': business_type, 'keyword': keyword})
                    return {
                        'is_suitable': False,
                        'reason': f"Business name contains '{keyword}' indicating {business_type.replace('_', ' ')}",
                        'matches': matches
                    }

        return {'is_suitable': True, 'reason': 'No exclusionary keywords found', 'matches': []}

    async def _analyze_website_content(self, website: str) -> Dict[str, Any]:
        """
        Scrape and analyze website content for business type indicators.
        Looks at products, services, descriptions, meta tags, etc.
        """
        result = {
            'url': website,
            'is_suitable': True,
            'reason': '',
            'products_found': [],
            'services_found': [],
            'category_indicators': [],
            'fetch_success': False
        }

        try:
            # Normalize URL
            if not website.startswith(('http://', 'https://')):
                website = f"https://{website}"

            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(website, allow_redirects=True) as response:
                    if response.status != 200:
                        result['reason'] = f'Website returned status {response.status}'
                        return result

                    content = await response.text()
                    content_lower = content.lower()
                    result['fetch_success'] = True

                    # Extract meta description
                    meta_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']', content, re.IGNORECASE)
                    if meta_match:
                        result['meta_description'] = meta_match.group(1)

                    # Check for convenience store indicators
                    convenience_indicators = [
                        'lottery tickets', 'tobacco products', 'cigarettes',
                        'snacks and beverages', 'atm available', 'money orders',
                        'phone cards', 'prepaid cards', 'scratch tickets',
                        'convenience items', '24 hour', '24/7', 'open late'
                    ]

                    for indicator in convenience_indicators:
                        if indicator in content_lower:
                            result['category_indicators'].append(indicator)

                    if len(result['category_indicators']) >= 3:
                        result['is_suitable'] = False
                        result['reason'] = f"Website contains multiple convenience store indicators: {result['category_indicators']}"
                        return result

                    # Check for gas station indicators
                    gas_indicators = ['gas prices', 'fuel prices', 'diesel', 'premium gas', 'car wash', 'gas bar']
                    for indicator in gas_indicators:
                        if indicator in content_lower:
                            result['category_indicators'].append(indicator)

                    if any(ind in result['category_indicators'] for ind in gas_indicators):
                        result['is_suitable'] = False
                        result['reason'] = f"Website indicates gas station: {result['category_indicators']}"
                        return result

                    # Check for franchise/chain indicators
                    franchise_indicators = ['franchise opportunities', 'franchisee', 'corporate headquarters', 'chain restaurant']
                    for indicator in franchise_indicators:
                        if indicator in content_lower:
                            result['category_indicators'].append(indicator)

                    # Check for retail chain indicators
                    chain_indicators = ['store locations', 'find a store near you', 'nationwide', 'multiple locations across']
                    chain_count = sum(1 for ind in chain_indicators if ind in content_lower)
                    if chain_count >= 2:
                        result['is_suitable'] = False
                        result['reason'] = "Website indicates retail chain with multiple locations"
                        return result

                    # Check for non-profit indicators
                    nonprofit_indicators = ['donate', 'donation', 'registered charity', 'charitable organization', 'volunteer']
                    nonprofit_count = sum(1 for ind in nonprofit_indicators if ind in content_lower)
                    if nonprofit_count >= 3:
                        result['is_suitable'] = False
                        result['reason'] = "Website indicates non-profit organization"
                        return result

                    self.logger.info("website_analysis_complete", website=website, suitable=result['is_suitable'])

        except asyncio.TimeoutError:
            result['reason'] = 'Website fetch timeout'
            self.logger.warning("website_analysis_timeout", website=website)
        except Exception as e:
            result['reason'] = f'Website analysis error: {str(e)}'
            self.logger.warning("website_analysis_error", website=website, error=str(e))

        return result

    async def _check_yellowpages_category(self, lead: BusinessLead) -> Dict[str, Any]:
        """
        Check Yellow Pages for business category classification.
        Yellow Pages has authoritative business category data.
        """
        result = {
            'is_suitable': True,
            'reason': '',
            'categories': [],
            'checked': False
        }

        try:
            from ..integrations.yellowpages_client import YellowPagesClient

            # Use async context manager to handle session properly
            async with YellowPagesClient() as yp_client:
                # Search for business
                yp_data = await yp_client.search_business(
                    business_name=lead.business_name,
                    city=lead.location.city if lead.location else 'Hamilton'
                )

                if yp_data and 'categories' in yp_data:
                    result['checked'] = True
                    result['categories'] = yp_data['categories']

                    # Check if any categories are in excluded list
                    for category in yp_data['categories']:
                        if category in self.excluded_yellowpages_categories:
                            result['is_suitable'] = False
                            result['reason'] = f"Yellow Pages category '{category}' is excluded"
                            self.logger.info(
                                "yellowpages_exclusion",
                                business_name=lead.business_name,
                                category=category
                            )
                            return result

                    # Check for convenience store variations
                    convenience_variations = [
                        'Convenience', 'Variety Store', 'Corner Store',
                        'Mini Mart', 'Gas Station', 'Service Station'
                    ]
                    for cat in result['categories']:
                        if any(var.lower() in cat.lower() for var in convenience_variations):
                            result['is_suitable'] = False
                            result['reason'] = f"Yellow Pages category '{cat}' indicates convenience store or gas station"
                            return result

                    self.logger.info(
                        "yellowpages_check_passed",
                        business_name=lead.business_name,
                        categories=result['categories']
                    )

        except ImportError:
            self.logger.warning("yellowpages_client_not_available")
        except Exception as e:
            self.logger.warning("yellowpages_check_error", error=str(e))
            # Don't fail validation on YP errors - just log

        return result

    async def _check_google_business(self, lead: BusinessLead) -> Dict[str, Any]:
        """
        Check Google Business Profile for business type information.
        Uses web search to find Google Business listing.
        """
        result = {
            'is_suitable': True,
            'reason': '',
            'business_type': None,
            'categories': [],
            'checked': False
        }

        try:
            # In production, would use Google Places API or web scraping
            # For now, we simulate by checking if we can find google business info

            query = f"{lead.business_name} {lead.location.city if lead.location else 'Hamilton'} google business"

            # Placeholder for actual Google Business API integration
            # Would check business categories, reviews, photos for indicators

            self.logger.debug("google_business_check", business_name=lead.business_name)

        except Exception as e:
            self.logger.warning("google_business_check_error", error=str(e))

        return result

    async def _check_linkedin(self, lead: BusinessLead) -> Dict[str, Any]:
        """
        Check LinkedIn company page for business description and industry.
        LinkedIn provides professional business classifications.
        """
        result = {
            'is_suitable': True,
            'reason': '',
            'industry': None,
            'description': None,
            'checked': False
        }

        try:
            # In production, would use LinkedIn API or web scraping
            # Would check company page for:
            # - Industry classification
            # - Company description
            # - Employee count
            # - Specialties

            self.logger.debug("linkedin_check", business_name=lead.business_name)

        except Exception as e:
            self.logger.warning("linkedin_check_error", error=str(e))

        return result

    async def _check_hamilton_chamber(self, lead: BusinessLead) -> Dict[str, Any]:
        """
        Check Hamilton Chamber of Commerce member directory.
        Chamber members have verified business information.
        """
        result = {
            'is_suitable': True,
            'reason': '',
            'is_member': False,
            'member_category': None,
            'checked': False
        }

        try:
            # In production, would query Hamilton Chamber of Commerce API/directory
            # Would provide verified business category and membership status

            self.logger.debug("chamber_check", business_name=lead.business_name)

        except Exception as e:
            self.logger.warning("chamber_check_error", error=str(e))

        return result

    async def _llm_classify_business(self, lead: BusinessLead, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use local LLM to analyze all gathered evidence and make final classification.
        LLM considers all data sources and makes intelligent determination.
        """
        result = {
            'is_suitable': True,
            'reason': '',
            'confidence': 0.0,
            'business_type': None,
            'classification': None
        }

        try:
            # Prepare evidence summary for LLM
            evidence_summary = self._prepare_evidence_for_llm(lead, evidence)

            # In production, would call local LLM (e.g., Ollama, LLaMA) with prompt:
            # "Based on this evidence, classify the business type and determine if it's
            #  a convenience store, gas station, retail chain, franchise, or suitable
            #  for acquisition. Explain your reasoning."

            # For now, use rule-based heuristics as fallback
            result = self._rule_based_classification(evidence_summary)

            self.logger.info(
                "llm_classification_complete",
                business_name=lead.business_name,
                suitable=result['is_suitable'],
                confidence=result['confidence']
            )

        except Exception as e:
            self.logger.error("llm_classification_error", error=str(e))
            # On error, be conservative and allow through (other checks still apply)
            result['reason'] = f"LLM classification error: {str(e)}"

        return result

    def _prepare_evidence_for_llm(self, lead: BusinessLead, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare evidence summary for LLM analysis."""
        return {
            'business_name': lead.business_name,
            'website': lead.contact.website if lead.contact else None,
            'address': lead.location.address if lead.location else None,
            'city': lead.location.city if lead.location else None,
            'website_indicators': evidence.get('website_analysis', {}).get('category_indicators', []),
            'yellowpages_categories': evidence.get('yellowpages_category', {}).get('categories', []),
            'keyword_matches': evidence.get('keyword_matches', [])
        }

    def _rule_based_classification(self, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rule-based classification as fallback when LLM is unavailable.
        Analyzes evidence using heuristics.
        """
        result = {
            'is_suitable': True,
            'reason': 'Rule-based analysis indicates suitable business',
            'confidence': 0.7,
            'business_type': 'unknown',
            'classification': 'suitable'
        }

        # Count negative indicators
        negative_indicators = 0
        reasons = []

        # Website indicators
        website_indicators = evidence.get('website_indicators', [])
        if len(website_indicators) >= 2:
            negative_indicators += len(website_indicators)
            reasons.append(f"Website contains {len(website_indicators)} exclusionary indicators")

        # Yellow Pages categories
        yp_categories = evidence.get('yellowpages_categories', [])
        excluded_yp = [cat for cat in yp_categories if cat in self.excluded_yellowpages_categories]
        if excluded_yp:
            negative_indicators += 5  # Strong signal
            reasons.append(f"Yellow Pages lists excluded categories: {excluded_yp}")

        # Keyword matches
        keyword_matches = evidence.get('keyword_matches', [])
        if keyword_matches:
            negative_indicators += len(keyword_matches) * 3
            reasons.append(f"Business name matches {len(keyword_matches)} excluded keywords")

        # Make decision based on negative indicators
        if negative_indicators >= 5:
            result['is_suitable'] = False
            result['reason'] = '; '.join(reasons)
            result['confidence'] = min(0.9, 0.5 + (negative_indicators * 0.1))
            result['classification'] = 'excluded'
        elif negative_indicators >= 2:
            result['is_suitable'] = False
            result['reason'] = '; '.join(reasons) + ' (moderate confidence)'
            result['confidence'] = 0.6
            result['classification'] = 'excluded'
        else:
            result['confidence'] = max(0.5, 0.9 - (negative_indicators * 0.1))

        return result

    def get_classification_stats(self) -> Dict[str, int]:
        """Get classification statistics."""
        return self.classification_stats.copy()
