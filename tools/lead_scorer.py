"""
Advanced Lead Scoring System with Machine Learning
Multi-factor scoring algorithm for business acquisition lead prioritization.
"""

import os
import logging
import pickle
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import sqlite3
from pathlib import Path

try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
    from sklearn.preprocessing import StandardScaler, LabelEncoder
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, mean_squared_error
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("scikit-learn not available. Using rule-based scoring only.")

logger = logging.getLogger(__name__)

@dataclass
class LeadScore:
    business_name: str
    total_score: float
    factor_scores: Dict[str, float]
    prediction_confidence: float
    risk_assessment: str
    priority_level: str
    recommended_action: str
    scoring_timestamp: datetime

class LeadScorer:
    """Advanced lead scoring with machine learning and rule-based components."""

    def __init__(self, db_path: str = "data/lead_scoring.db", model_path: str = "models/"):
        self.db_path = db_path
        self.model_path = Path(model_path)
        self.model_path.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_database()

        # Scoring factors and weights
        self.score_factors = {
            'revenue_confirmed': {
                'weight': 30,
                'description': 'Verified through multiple sources',
                'max_score': 30
            },
            'years_in_business': {
                'weight': 20,
                'description': 'Cross-referenced with incorporation data',
                'max_score': 20
            },
            'owner_identified': {
                'weight': 15,
                'description': 'Direct decision maker found',
                'max_score': 15
            },
            'financial_health': {
                'weight': 15,
                'description': 'Credit scores, liens check',
                'max_score': 15
            },
            'engagement_signals': {
                'weight': 10,
                'description': 'Website activity, social media',
                'max_score': 10
            },
            'market_position': {
                'weight': 10,
                'description': 'Reviews, competitors, market share',
                'max_score': 10
            }
        }

        # Load or initialize ML models
        self.ml_model = None
        self.scaler = None
        self.label_encoders = {}

        if ML_AVAILABLE:
            self._load_or_create_models()

        # Scoring thresholds
        self.thresholds = {
            'hot_lead': 80,      # 80+ points = hot lead
            'warm_lead': 60,     # 60-79 points = warm lead
            'cold_lead': 40,     # 40-59 points = cold lead
            'reject': 40         # <40 points = reject
        }

    def _init_database(self):
        """Initialize SQLite database for scoring history."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scoring_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    business_name TEXT NOT NULL,
                    total_score REAL NOT NULL,
                    factor_scores TEXT,
                    prediction_confidence REAL,
                    priority_level TEXT,
                    outcome TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def _load_or_create_models(self):
        """Load existing ML models or create new ones."""
        model_file = self.model_path / "lead_scoring_model.pkl"
        scaler_file = self.model_path / "scaler.pkl"

        try:
            if model_file.exists() and scaler_file.exists():
                with open(model_file, 'rb') as f:
                    self.ml_model = pickle.load(f)
                with open(scaler_file, 'rb') as f:
                    self.scaler = pickle.load(f)
                logger.info("Loaded existing ML models")
            else:
                logger.info("Creating new ML models")
                self._create_new_models()
        except Exception as e:
            logger.error(f"Failed to load ML models: {e}")
            self._create_new_models()

    def _create_new_models(self):
        """Create and train new ML models."""
        if not ML_AVAILABLE:
            return

        try:
            # Create initial models
            self.ml_model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )
            self.scaler = StandardScaler()

            # Generate synthetic training data for initial model
            synthetic_data = self._generate_synthetic_training_data()
            if len(synthetic_data) > 0:
                self._train_models(synthetic_data)

        except Exception as e:
            logger.error(f"Failed to create ML models: {e}")

    def _generate_synthetic_training_data(self) -> pd.DataFrame:
        """Generate synthetic training data for initial model training."""
        np.random.seed(42)

        # Generate 1000 synthetic business records
        n_samples = 1000

        data = {
            'revenue': np.random.normal(1200000, 200000, n_samples),
            'years_in_business': np.random.exponential(8, n_samples),
            'employee_count': np.random.poisson(20, n_samples),
            'credit_score': np.random.normal(75, 15, n_samples),
            'website_quality': np.random.uniform(0, 100, n_samples),
            'owner_age': np.random.normal(55, 10, n_samples),
            'industry_growth': np.random.normal(0.05, 0.02, n_samples),
            'local_competition': np.random.poisson(5, n_samples),
            'social_media_presence': np.random.uniform(0, 100, n_samples),
            'financial_stability': np.random.uniform(0, 100, n_samples)
        }

        df = pd.DataFrame(data)

        # Create target variable (success rate) based on business logic
        df['success_probability'] = (
            (df['revenue'].between(1000000, 1400000).astype(int) * 0.3) +
            (df['years_in_business'] >= 3).astype(int) * 0.2 +
            (df['credit_score'] >= 70).astype(int) * 0.15 +
            (df['website_quality'] >= 60).astype(int) * 0.1 +
            (df['owner_age'].between(50, 65)).astype(int) * 0.1 +
            (df['financial_stability'] >= 70).astype(int) * 0.15
        )

        # Add noise and create binary target
        df['success_probability'] += np.random.normal(0, 0.1, n_samples)
        df['is_successful'] = (df['success_probability'] > 0.6).astype(int)

        return df

    def _train_models(self, training_data: pd.DataFrame):
        """Train ML models with provided data."""
        try:
            # Prepare features
            feature_columns = [
                'revenue', 'years_in_business', 'employee_count', 'credit_score',
                'website_quality', 'owner_age', 'industry_growth', 'local_competition',
                'social_media_presence', 'financial_stability'
            ]

            X = training_data[feature_columns]
            y = training_data['is_successful']

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

            # Scale features
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)

            # Train model
            self.ml_model.fit(X_train_scaled, y_train)

            # Evaluate model
            train_score = self.ml_model.score(X_train_scaled, y_train)
            test_score = self.ml_model.score(X_test_scaled, y_test)

            logger.info(f"Model trained - Train score: {train_score:.3f}, Test score: {test_score:.3f}")

            # Save models
            self._save_models()

        except Exception as e:
            logger.error(f"Model training failed: {e}")

    def _save_models(self):
        """Save trained models to disk."""
        try:
            model_file = self.model_path / "lead_scoring_model.pkl"
            scaler_file = self.model_path / "scaler.pkl"

            with open(model_file, 'wb') as f:
                pickle.dump(self.ml_model, f)
            with open(scaler_file, 'wb') as f:
                pickle.dump(self.scaler, f)

            logger.info("Models saved successfully")
        except Exception as e:
            logger.error(f"Failed to save models: {e}")

    def calculate_rule_based_score(self, business: Dict[str, Any],
                                 validation_results: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
        """Calculate rule-based scores for each factor."""
        factor_scores = {}

        # Revenue confirmation score
        revenue = business.get('revenue', 0)
        if 1000000 <= revenue <= 1400000:
            factor_scores['revenue_confirmed'] = self.score_factors['revenue_confirmed']['max_score']
        elif revenue > 0:
            # Partial score based on how close to target range
            if revenue < 1000000:
                factor_scores['revenue_confirmed'] = max(0, (revenue / 1000000) * 15)
            else:  # revenue > 1400000
                factor_scores['revenue_confirmed'] = max(0, 30 - ((revenue - 1400000) / 100000))
        else:
            factor_scores['revenue_confirmed'] = 0

        # Business age score
        years_in_business = business.get('years_in_business', 0)
        if years_in_business >= 10:
            factor_scores['years_in_business'] = self.score_factors['years_in_business']['max_score']
        elif years_in_business >= 3:
            factor_scores['years_in_business'] = (years_in_business / 10) * 20
        else:
            factor_scores['years_in_business'] = 0

        # Owner identification score
        contacts = business.get('contacts', [])
        decision_makers = [
            contact for contact in contacts
            if any(role in contact.get('title', '').lower()
                  for role in ['owner', 'president', 'ceo', 'founder'])
        ]

        if decision_makers:
            # Check if contact is validated
            if validation_results and validation_results.get('contact_validated'):
                factor_scores['owner_identified'] = self.score_factors['owner_identified']['max_score']
            else:
                factor_scores['owner_identified'] = 10  # Partial score if not validated
        else:
            factor_scores['owner_identified'] = 0

        # Financial health score
        credit_score = business.get('credit_score', 0)
        if credit_score >= 80:
            factor_scores['financial_health'] = self.score_factors['financial_health']['max_score']
        elif credit_score >= 60:
            factor_scores['financial_health'] = (credit_score / 80) * 15
        else:
            factor_scores['financial_health'] = 0

        # Engagement signals score
        website_quality = business.get('website_quality', 0)
        social_media = business.get('social_media_presence', 0)
        engagement_score = (website_quality + social_media) / 2

        if engagement_score >= 70:
            factor_scores['engagement_signals'] = self.score_factors['engagement_signals']['max_score']
        elif engagement_score >= 40:
            factor_scores['engagement_signals'] = (engagement_score / 70) * 10
        else:
            factor_scores['engagement_signals'] = 0

        # Market position score
        reviews_score = business.get('reviews_score', 0)
        market_share = business.get('market_share', 0)
        position_score = (reviews_score + market_share) / 2

        if position_score >= 70:
            factor_scores['market_position'] = self.score_factors['market_position']['max_score']
        elif position_score >= 40:
            factor_scores['market_position'] = (position_score / 70) * 10
        else:
            factor_scores['market_position'] = 0

        return factor_scores

    def calculate_ml_score(self, business: Dict[str, Any]) -> Tuple[float, float]:
        """Calculate ML-based score and confidence."""
        if not ML_AVAILABLE or not self.ml_model or not self.scaler:
            return 0.0, 0.0

        try:
            # Prepare features for ML model
            features = np.array([[
                business.get('revenue', 0),
                business.get('years_in_business', 0),
                business.get('employee_count', 0),
                business.get('credit_score', 0),
                business.get('website_quality', 0),
                business.get('owner_age', 55),
                business.get('industry_growth', 0.05),
                business.get('local_competition', 5),
                business.get('social_media_presence', 0),
                business.get('financial_stability', 0)
            ]])

            # Scale features
            features_scaled = self.scaler.transform(features)

            # Get prediction probability
            prediction_proba = self.ml_model.predict_proba(features_scaled)[0]
            ml_score = prediction_proba[1] * 100  # Probability of success * 100

            # Calculate confidence based on how decisive the prediction is
            confidence = abs(prediction_proba[1] - 0.5) * 2  # 0 to 1 scale

            return ml_score, confidence

        except Exception as e:
            logger.error(f"ML scoring failed: {e}")
            return 0.0, 0.0

    def score_lead(self, business: Dict[str, Any],
                  validation_results: Optional[Dict[str, Any]] = None) -> LeadScore:
        """Main scoring method that combines rule-based and ML approaches."""
        logger.info(f"Scoring lead: {business.get('name', 'Unknown')}")

        # Calculate rule-based scores
        factor_scores = self.calculate_rule_based_score(business, validation_results)
        rule_based_total = sum(factor_scores.values())

        # Calculate ML score
        ml_score, ml_confidence = self.calculate_ml_score(business)

        # Combine scores (weighted average)
        if ML_AVAILABLE and self.ml_model:
            # 70% rule-based, 30% ML
            total_score = (rule_based_total * 0.7) + (ml_score * 0.3)
            prediction_confidence = ml_confidence
        else:
            total_score = rule_based_total
            prediction_confidence = 0.8  # Default confidence for rule-based

        # Determine priority level and risk assessment
        priority_level, risk_assessment = self._assess_priority_and_risk(
            total_score, factor_scores, validation_results
        )

        # Generate recommendation
        recommended_action = self._generate_recommendation(
            total_score, priority_level, factor_scores
        )

        # Store scoring history
        self._store_scoring_history(business, total_score, factor_scores,
                                  prediction_confidence, priority_level)

        return LeadScore(
            business_name=business.get('name', 'Unknown'),
            total_score=total_score,
            factor_scores=factor_scores,
            prediction_confidence=prediction_confidence,
            risk_assessment=risk_assessment,
            priority_level=priority_level,
            recommended_action=recommended_action,
            scoring_timestamp=datetime.now()
        )

    def _assess_priority_and_risk(self, total_score: float, factor_scores: Dict[str, float],
                                validation_results: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        """Assess priority level and risk based on score and factors."""
        # Determine priority level
        if total_score >= self.thresholds['hot_lead']:
            priority_level = "HOT"
        elif total_score >= self.thresholds['warm_lead']:
            priority_level = "WARM"
        elif total_score >= self.thresholds['cold_lead']:
            priority_level = "COLD"
        else:
            priority_level = "REJECT"

        # Assess risk factors
        risk_factors = []

        if factor_scores.get('revenue_confirmed', 0) < 15:
            risk_factors.append("Revenue not confirmed")
        if factor_scores.get('financial_health', 0) < 8:
            risk_factors.append("Poor financial health")
        if factor_scores.get('owner_identified', 0) < 8:
            risk_factors.append("Decision maker not identified")

        if not risk_factors:
            risk_assessment = "LOW RISK"
        elif len(risk_factors) == 1:
            risk_assessment = "MEDIUM RISK"
        else:
            risk_assessment = "HIGH RISK"

        return priority_level, risk_assessment

    def _generate_recommendation(self, total_score: float, priority_level: str,
                               factor_scores: Dict[str, float]) -> str:
        """Generate actionable recommendation based on scoring results."""
        if priority_level == "HOT":
            return "IMMEDIATE ACTION: Contact within 24 hours. High probability of success."
        elif priority_level == "WARM":
            weak_factors = [
                factor for factor, score in factor_scores.items()
                if score < self.score_factors[factor]['max_score'] * 0.5
            ]
            if weak_factors:
                return f"INVESTIGATE: Research {', '.join(weak_factors)} before contact."
            else:
                return "SCHEDULE: Contact within 3-5 business days."
        elif priority_level == "COLD":
            return "LOW PRIORITY: Consider only if no higher priority leads available."
        else:
            return "DO NOT PURSUE: Score too low for viable opportunity."

    def _store_scoring_history(self, business: Dict[str, Any], total_score: float,
                             factor_scores: Dict[str, float], confidence: float,
                             priority_level: str):
        """Store scoring results in database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO scoring_history
                    (business_name, total_score, factor_scores, prediction_confidence,
                     priority_level)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    business.get('name', 'Unknown'),
                    total_score,
                    str(factor_scores),
                    confidence,
                    priority_level
                ))
        except Exception as e:
            logger.error(f"Failed to store scoring history: {e}")

    def batch_score_leads(self, businesses: List[Dict[str, Any]]) -> List[LeadScore]:
        """Score multiple leads and return sorted by priority."""
        scored_leads = []

        for business in businesses:
            try:
                score = self.score_lead(business)
                scored_leads.append(score)
            except Exception as e:
                logger.error(f"Failed to score {business.get('name', 'Unknown')}: {e}")

        # Sort by total score (descending)
        scored_leads.sort(key=lambda x: x.total_score, reverse=True)

        return scored_leads

    def retrain_model(self, feedback_data: pd.DataFrame):
        """Retrain ML model with new feedback data."""
        if not ML_AVAILABLE:
            logger.warning("ML not available for retraining")
            return

        try:
            # Combine with existing synthetic data
            synthetic_data = self._generate_synthetic_training_data()
            combined_data = pd.concat([synthetic_data, feedback_data], ignore_index=True)

            self._train_models(combined_data)
            logger.info("Model retrained successfully")

        except Exception as e:
            logger.error(f"Model retraining failed: {e}")

    def get_scoring_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Get analytics on scoring performance over time."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)

            with sqlite3.connect(self.db_path) as conn:
                query = """
                    SELECT
                        priority_level,
                        COUNT(*) as count,
                        AVG(total_score) as avg_score,
                        outcome
                    FROM scoring_history
                    WHERE created_at >= ?
                    GROUP BY priority_level, outcome
                """

                df = pd.read_sql_query(query, conn, params=(cutoff_date.isoformat(),))

                return {
                    'total_scored': len(df),
                    'priority_breakdown': df.groupby('priority_level')['count'].sum().to_dict(),
                    'average_scores': df.groupby('priority_level')['avg_score'].mean().to_dict(),
                    'conversion_rates': df[df['outcome'].notna()].groupby('priority_level')['outcome'].apply(
                        lambda x: (x == 'success').mean()
                    ).to_dict()
                }

        except Exception as e:
            logger.error(f"Failed to get analytics: {e}")
            return {}

if __name__ == "__main__":
    # Test the scoring system
    scorer = LeadScorer()

    test_business = {
        'name': 'Test Manufacturing Inc.',
        'revenue': 1200000,
        'years_in_business': 8,
        'employee_count': 25,
        'credit_score': 78,
        'website_quality': 85,
        'owner_age': 58,
        'industry_growth': 0.07,
        'local_competition': 3,
        'social_media_presence': 65,
        'financial_stability': 80,
        'contacts': [
            {
                'name': 'John Owner',
                'title': 'President',
                'email': 'john@testmfg.com'
            }
        ]
    }

    score_result = scorer.score_lead(test_business)

    print(f"Business: {score_result.business_name}")
    print(f"Total Score: {score_result.total_score:.2f}")
    print(f"Priority: {score_result.priority_level}")
    print(f"Risk: {score_result.risk_assessment}")
    print(f"Recommendation: {score_result.recommended_action}")
    print("\nFactor Scores:")
    for factor, score in score_result.factor_scores.items():
        print(f"  {factor}: {score:.1f}")