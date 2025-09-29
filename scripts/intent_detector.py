"""
Business Intent Detection System
Identifies buying signals and acquisition intent for business owners.
"""

import os
import re
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import requests
from requests_cache import CachedSession
import sqlite3
from pathlib import Path
import json

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

@dataclass
class IntentSignal:
    signal_type: str
    confidence: float
    evidence: List[str]
    source: str
    detected_at: datetime

@dataclass
class IntentAnalysis:
    business_name: str
    overall_intent_score: float
    detected_signals: List[IntentSignal]
    buying_probability: float
    urgency_level: str
    recommended_approach: str
    analysis_timestamp: datetime

class IntentDetector:
    """Advanced intent detection for business acquisition opportunities."""

    def __init__(self, db_path: str = "data/intent_detection.db"):
        self.db_path = db_path
        self.session = CachedSession(
            cache_name='intent_cache',
            expire_after=7200  # 2 hour cache for intent data
        )

        # Initialize database
        self._init_database()

        # Intent signal definitions with weights
        self.buying_signals = {
            'retirement_mentions': {
                'weight': 0.30,
                'keywords': [
                    'retire', 'retirement', 'stepping down', 'successor',
                    'next generation', 'legacy', 'transition', 'passing torch'
                ],
                'description': 'Owner approaching retirement age or mentioning retirement'
            },
            'no_succession_plan': {
                'weight': 0.25,
                'keywords': [
                    'no successor', 'no one to take over', 'children not interested',
                    'family not involved', 'no heir', 'succession planning'
                ],
                'description': 'Lack of clear succession planning'
            },
            'declining_revenue': {
                'weight': 0.20,
                'keywords': [
                    'struggling', 'declining sales', 'lost customers', 'competition',
                    'economic pressure', 'downturn', 'challenging times'
                ],
                'description': 'Revenue decline or business challenges'
            },
            'industry_consolidation': {
                'weight': 0.15,
                'keywords': [
                    'consolidation', 'merger', 'acquisition', 'bigger players',
                    'market changes', 'industry shift', 'need scale'
                ],
                'description': 'Industry consolidation pressures'
            },
            'lease_expiration': {
                'weight': 0.10,
                'keywords': [
                    'lease expiring', 'rent increase', 'relocating', 'property sale',
                    'landlord selling', 'lease renewal', 'moving costs'
                ],
                'description': 'Property or lease-related pressures'
            }
        }

        # Age-based retirement probability
        self.retirement_age_probabilities = {
            (55, 60): 0.2,   # 20% probability
            (60, 65): 0.5,   # 50% probability
            (65, 70): 0.8,   # 80% probability
            (70, 100): 0.95  # 95% probability
        }

    def _init_database(self):
        """Initialize SQLite database for intent tracking."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS intent_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    business_name TEXT NOT NULL,
                    overall_intent_score REAL,
                    buying_probability REAL,
                    urgency_level TEXT,
                    detected_signals TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def check_owner_age(self, business: Dict[str, Any]) -> IntentSignal:
        """Check owner age for retirement signals."""
        logger.info(f"Checking owner age for {business.get('name', 'Unknown')}")

        evidence = []
        confidence = 0.0

        try:
            contacts = business.get('contacts', [])
            owner_ages = []

            for contact in contacts:
                title = contact.get('title', '').lower()
                if any(role in title for role in ['owner', 'president', 'ceo', 'founder']):
                    age = contact.get('age')
                    if age:
                        owner_ages.append(age)
                        evidence.append(f"Owner age: {age}")

            if owner_ages:
                avg_age = sum(owner_ages) / len(owner_ages)

                # Determine retirement probability based on age
                for age_range, probability in self.retirement_age_probabilities.items():
                    if age_range[0] <= avg_age < age_range[1]:
                        confidence = probability
                        break

                if avg_age >= 55:
                    evidence.append(f"Average owner age ({avg_age:.0f}) indicates potential retirement timeline")
                else:
                    evidence.append(f"Owner age ({avg_age:.0f}) below typical retirement consideration")

            else:
                # Try to infer age from business age and other factors
                years_in_business = business.get('years_in_business', 0)
                if years_in_business > 20:
                    confidence = 0.3
                    evidence.append("Business age suggests potential owner retirement consideration")

        except Exception as e:
            logger.error(f"Owner age check failed: {e}")
            evidence.append(f"Error checking owner age: {e}")

        return IntentSignal(
            signal_type='retirement_mentions',
            confidence=confidence,
            evidence=evidence,
            source='owner_demographics',
            detected_at=datetime.now()
        )

    def analyze_company_structure(self, business: Dict[str, Any]) -> IntentSignal:
        """Analyze company structure for succession planning."""
        logger.info(f"Analyzing succession planning for {business.get('name', 'Unknown')}")

        evidence = []
        confidence = 0.0

        try:
            # Check for family members in business
            contacts = business.get('contacts', [])
            family_indicators = ['jr', 'sr', 'son', 'daughter', 'family']

            family_involved = any(
                any(indicator in contact.get('name', '').lower() or
                    indicator in contact.get('title', '').lower()
                    for indicator in family_indicators)
                for contact in contacts
            )

            if family_involved:
                confidence = 0.2
                evidence.append("Family members appear to be involved in business")
            else:
                confidence = 0.6
                evidence.append("No clear family succession apparent")

            # Check company age vs owner involvement
            years_in_business = business.get('years_in_business', 0)
            if years_in_business > 15:
                confidence += 0.2
                evidence.append("Long-established business may lack succession planning")

            # Check for management structure
            management_titles = ['coo', 'cto', 'vp', 'director', 'manager']
            management_present = any(
                any(title in contact.get('title', '').lower() for title in management_titles)
                for contact in contacts
            )

            if not management_present:
                confidence += 0.2
                evidence.append("Limited management structure suggests owner-dependent operations")

            confidence = min(1.0, confidence)

        except Exception as e:
            logger.error(f"Company structure analysis failed: {e}")
            evidence.append(f"Error analyzing structure: {e}")

        return IntentSignal(
            signal_type='no_succession_plan',
            confidence=confidence,
            evidence=evidence,
            source='company_structure',
            detected_at=datetime.now()
        )

    def compare_historical_data(self, business: Dict[str, Any]) -> IntentSignal:
        """Compare historical performance data for decline signals."""
        logger.info(f"Analyzing historical performance for {business.get('name', 'Unknown')}")

        evidence = []
        confidence = 0.0

        try:
            # Check revenue trends
            current_revenue = business.get('revenue', 0)
            historical_revenue = business.get('historical_revenue', [])

            if historical_revenue and len(historical_revenue) > 1:
                # Calculate trend
                recent_avg = sum(historical_revenue[-2:]) / 2 if len(historical_revenue) >= 2 else historical_revenue[-1]
                older_avg = sum(historical_revenue[:-2]) / max(1, len(historical_revenue) - 2) if len(historical_revenue) > 2 else recent_avg

                if recent_avg < older_avg * 0.9:  # 10% decline
                    confidence = 0.7
                    evidence.append(f"Revenue decline detected: {((older_avg - recent_avg) / older_avg * 100):.1f}%")
                elif recent_avg < older_avg * 0.95:  # 5% decline
                    confidence = 0.4
                    evidence.append("Slight revenue decline trend")
                else:
                    confidence = 0.1
                    evidence.append("Revenue appears stable or growing")

            # Check market indicators
            industry = business.get('industry', '')
            if industry:
                industry_health = self._check_industry_health(industry)
                if industry_health and industry_health.get('declining'):
                    confidence += 0.3
                    evidence.append(f"Industry {industry} showing decline trends")

            # Check for business challenges mentioned
            business_description = business.get('description', '') + ' ' + business.get('notes', '')
            challenge_keywords = ['struggling', 'difficult', 'challenging', 'competition', 'pressure']

            if any(keyword in business_description.lower() for keyword in challenge_keywords):
                confidence += 0.2
                evidence.append("Business challenges mentioned in available information")

            confidence = min(1.0, confidence)

        except Exception as e:
            logger.error(f"Historical data analysis failed: {e}")
            evidence.append(f"Error analyzing historical data: {e}")

        return IntentSignal(
            signal_type='declining_revenue',
            confidence=confidence,
            evidence=evidence,
            source='historical_analysis',
            detected_at=datetime.now()
        )

    def track_market_trends(self, business: Dict[str, Any]) -> IntentSignal:
        """Track industry consolidation and market trends."""
        logger.info(f"Tracking market trends for {business.get('name', 'Unknown')}")

        evidence = []
        confidence = 0.0

        try:
            industry = business.get('industry', '')
            location = business.get('location', '')

            # Check for consolidation news
            consolidation_data = self._search_consolidation_news(industry, location)
            if consolidation_data:
                confidence = consolidation_data.get('confidence', 0.0)
                evidence.extend(consolidation_data.get('evidence', []))

            # Check competitor activity
            competitor_data = self._analyze_competitor_activity(industry, location)
            if competitor_data:
                confidence += competitor_data.get('confidence', 0.0) * 0.5
                evidence.extend(competitor_data.get('evidence', []))

            # Check for regulatory changes
            regulatory_data = self._check_regulatory_changes(industry)
            if regulatory_data:
                confidence += regulatory_data.get('confidence', 0.0) * 0.3
                evidence.extend(regulatory_data.get('evidence', []))

            confidence = min(1.0, confidence)

        except Exception as e:
            logger.error(f"Market trend analysis failed: {e}")
            evidence.append(f"Error tracking market trends: {e}")

        return IntentSignal(
            signal_type='industry_consolidation',
            confidence=confidence,
            evidence=evidence,
            source='market_analysis',
            detected_at=datetime.now()
        )

    def check_property_records(self, business: Dict[str, Any]) -> IntentSignal:
        """Check property and lease records for pressure signals."""
        logger.info(f"Checking property records for {business.get('name', 'Unknown')}")

        evidence = []
        confidence = 0.0

        try:
            address = business.get('address', '')
            if address:
                # Check property ownership
                property_data = self._check_property_ownership(address)
                if property_data:
                    if property_data.get('for_sale'):
                        confidence = 0.8
                        evidence.append("Property is listed for sale")
                    elif property_data.get('lease_expires_soon'):
                        confidence = 0.6
                        evidence.append("Lease expiring within 12 months")

                # Check for recent property sales in area
                area_sales = self._check_area_property_sales(address)
                if area_sales and area_sales.get('recent_sales'):
                    confidence += 0.2
                    evidence.append("Recent commercial property sales in area")

            # Check for relocation mentions
            business_info = business.get('description', '') + ' ' + business.get('notes', '')
            relocation_keywords = ['relocating', 'moving', 'new location', 'lease', 'rent increase']

            if any(keyword in business_info.lower() for keyword in relocation_keywords):
                confidence += 0.3
                evidence.append("Relocation or lease concerns mentioned")

            confidence = min(1.0, confidence)

        except Exception as e:
            logger.error(f"Property records check failed: {e}")
            evidence.append(f"Error checking property records: {e}")

        return IntentSignal(
            signal_type='lease_expiration',
            confidence=confidence,
            evidence=evidence,
            source='property_records',
            detected_at=datetime.now()
        )

    def detect_intent(self, business: Dict[str, Any]) -> IntentAnalysis:
        """Main method to detect buying intent signals."""
        logger.info(f"Detecting intent for {business.get('name', 'Unknown')}")

        # Run all signal detection methods
        signals = [
            self.check_owner_age(business),
            self.analyze_company_structure(business),
            self.compare_historical_data(business),
            self.track_market_trends(business),
            self.check_property_records(business)
        ]

        # Filter out signals with zero confidence
        detected_signals = [signal for signal in signals if signal.confidence > 0.1]

        # Calculate overall intent score
        total_weighted_score = sum(
            signal.confidence * self.buying_signals[signal.signal_type]['weight']
            for signal in detected_signals
            if signal.signal_type in self.buying_signals
        )

        overall_intent_score = min(1.0, total_weighted_score)

        # Calculate buying probability
        buying_probability = self._calculate_buying_probability(overall_intent_score, detected_signals)

        # Determine urgency level
        urgency_level = self._determine_urgency_level(overall_intent_score, detected_signals)

        # Generate recommended approach
        recommended_approach = self._generate_approach_recommendation(
            overall_intent_score, urgency_level, detected_signals
        )

        # Store analysis
        self._store_intent_analysis(business, overall_intent_score, buying_probability,
                                  urgency_level, detected_signals)

        return IntentAnalysis(
            business_name=business.get('name', 'Unknown'),
            overall_intent_score=overall_intent_score,
            detected_signals=detected_signals,
            buying_probability=buying_probability,
            urgency_level=urgency_level,
            recommended_approach=recommended_approach,
            analysis_timestamp=datetime.now()
        )

    def _calculate_buying_probability(self, intent_score: float, signals: List[IntentSignal]) -> float:
        """Calculate probability of successful acquisition based on intent signals."""
        base_probability = intent_score * 0.7  # Base probability from intent score

        # Boost for specific high-value signals
        for signal in signals:
            if signal.signal_type == 'retirement_mentions' and signal.confidence > 0.6:
                base_probability += 0.15
            elif signal.signal_type == 'no_succession_plan' and signal.confidence > 0.7:
                base_probability += 0.10

        return min(1.0, base_probability)

    def _determine_urgency_level(self, intent_score: float, signals: List[IntentSignal]) -> str:
        """Determine urgency level based on intent signals."""
        if intent_score >= 0.7:
            return "HIGH"
        elif intent_score >= 0.4:
            return "MEDIUM"
        elif intent_score >= 0.2:
            return "LOW"
        else:
            return "MINIMAL"

    def _generate_approach_recommendation(self, intent_score: float, urgency_level: str,
                                        signals: List[IntentSignal]) -> str:
        """Generate recommended approach based on intent analysis."""
        if urgency_level == "HIGH":
            return "IMMEDIATE: Direct approach within 48 hours. High probability of receptiveness."
        elif urgency_level == "MEDIUM":
            primary_signals = [s.signal_type for s in signals if s.confidence > 0.5]
            if 'retirement_mentions' in primary_signals:
                return "PERSONAL: Focus on retirement planning and legacy preservation."
            elif 'declining_revenue' in primary_signals:
                return "BUSINESS: Emphasize growth opportunities and operational improvements."
            else:
                return "CONSULTATIVE: Explore business challenges and future planning."
        elif urgency_level == "LOW":
            return "EDUCATIONAL: Provide market insights and build relationship over time."
        else:
            return "PASSIVE: Monitor for changes, no immediate outreach recommended."

    def _store_intent_analysis(self, business: Dict[str, Any], intent_score: float,
                             buying_probability: float, urgency_level: str,
                             signals: List[IntentSignal]):
        """Store intent analysis in database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO intent_analysis
                    (business_name, overall_intent_score, buying_probability,
                     urgency_level, detected_signals)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    business.get('name', 'Unknown'),
                    intent_score,
                    buying_probability,
                    urgency_level,
                    json.dumps([{
                        'type': s.signal_type,
                        'confidence': s.confidence,
                        'evidence': s.evidence,
                        'source': s.source
                    } for s in signals])
                ))
        except Exception as e:
            logger.error(f"Failed to store intent analysis: {e}")

    # Helper methods for data source checks (simplified implementations)
    def _check_industry_health(self, industry: str) -> Optional[Dict[str, Any]]:
        """Check industry health indicators."""
        # Simplified implementation
        declining_industries = ['retail', 'traditional_manufacturing', 'print_media']
        return {'declining': industry.lower() in declining_industries}

    def _search_consolidation_news(self, industry: str, location: str) -> Optional[Dict[str, Any]]:
        """Search for industry consolidation news."""
        # Placeholder implementation
        return {'confidence': 0.3, 'evidence': ['Industry showing consolidation trends']}

    def _analyze_competitor_activity(self, industry: str, location: str) -> Optional[Dict[str, Any]]:
        """Analyze competitor acquisition activity."""
        return {'confidence': 0.2, 'evidence': ['Increased competitor activity in region']}

    def _check_regulatory_changes(self, industry: str) -> Optional[Dict[str, Any]]:
        """Check for regulatory changes affecting industry."""
        return {'confidence': 0.1, 'evidence': ['New regulations may impact industry']}

    def _check_property_ownership(self, address: str) -> Optional[Dict[str, Any]]:
        """Check property ownership and sale status."""
        return {'for_sale': False, 'lease_expires_soon': False}

    def _check_area_property_sales(self, address: str) -> Optional[Dict[str, Any]]:
        """Check recent property sales in area."""
        return {'recent_sales': True}

# Convenience functions for backward compatibility
buying_signals = {
    'retirement_mentions': lambda business: IntentDetector().check_owner_age(business),
    'no_succession_plan': lambda business: IntentDetector().analyze_company_structure(business),
    'declining_revenue': lambda business: IntentDetector().compare_historical_data(business),
    'industry_consolidation': lambda business: IntentDetector().track_market_trends(business),
    'lease_expiration': lambda business: IntentDetector().check_property_records(business)
}

if __name__ == "__main__":
    # Test the intent detection system
    detector = IntentDetector()

    test_business = {
        'name': 'Test Manufacturing Inc.',
        'industry': 'Manufacturing',
        'years_in_business': 25,
        'location': 'Hamilton, ON',
        'revenue': 1200000,
        'historical_revenue': [1400000, 1350000, 1200000, 1150000],
        'contacts': [
            {
                'name': 'John Smith Sr.',
                'title': 'Owner/President',
                'age': 62,
                'email': 'john@testmfg.com'
            }
        ],
        'address': '123 Industrial Way, Hamilton, ON',
        'description': 'Family-owned manufacturing business established 1998'
    }

    analysis = detector.detect_intent(test_business)

    print(f"Business: {analysis.business_name}")
    print(f"Intent Score: {analysis.overall_intent_score:.2f}")
    print(f"Buying Probability: {analysis.buying_probability:.2f}")
    print(f"Urgency: {analysis.urgency_level}")
    print(f"Approach: {analysis.recommended_approach}")
    print(f"\nDetected Signals:")
    for signal in analysis.detected_signals:
        print(f"  - {signal.signal_type}: {signal.confidence:.2f}")
        for evidence in signal.evidence:
            print(f"    • {evidence}")