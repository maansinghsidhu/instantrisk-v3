"""
XGBoost Model Loading and Prediction

Loads pre-trained models from S3 for frequency and severity prediction.
"""
import os
import json
import pickle
from typing import Dict, Any, Optional, Tuple
import logging

import boto3
import numpy as np
import pandas as pd
import xgboost as xgb

logger = logging.getLogger(__name__)

# Model cache in /tmp (persists across warm starts)
MODEL_CACHE: Dict[str, Any] = {}
S3_BUCKET = os.environ.get("RAPIDRATE_S3_BUCKET", "instantrisk-rapidrate-data")


def get_s3_client():
    """Get S3 client."""
    return boto3.client("s3")


def load_model(model_name: str) -> xgb.XGBRegressor:
    """Load XGBoost model from S3 or cache.

    Args:
        model_name: Model filename (without path)

    Returns:
        Loaded XGBoost model
    """
    if model_name in MODEL_CACHE:
        return MODEL_CACHE[model_name]

    # Check /tmp cache
    local_path = f"/tmp/{model_name}"
    if os.path.exists(local_path):
        logger.info(f"Loading model from local cache: {local_path}")
        with open(local_path, "rb") as f:
            model = pickle.load(f)
        MODEL_CACHE[model_name] = model
        return model

    # Download from S3
    s3_key = f"models/{model_name}"
    logger.info(f"Downloading model from S3: {S3_BUCKET}/{s3_key}")

    s3 = get_s3_client()
    s3.download_file(S3_BUCKET, s3_key, local_path)

    with open(local_path, "rb") as f:
        model = pickle.load(f)

    MODEL_CACHE[model_name] = model
    return model


def load_feature_config(policy_type: str) -> Dict[str, Any]:
    """Load feature configuration for a policy type.

    Args:
        policy_type: Policy type code (GL, WC, etc.)

    Returns:
        Feature configuration dict
    """
    config_name = f"{policy_type.lower()}_features.json"

    if config_name in MODEL_CACHE:
        return MODEL_CACHE[config_name]

    local_path = f"/tmp/{config_name}"

    if not os.path.exists(local_path):
        s3_key = f"config/{config_name}"
        s3 = get_s3_client()
        try:
            s3.download_file(S3_BUCKET, s3_key, local_path)
        except Exception as e:
            logger.warning(f"Could not load feature config: {e}")
            return get_default_feature_config()

    with open(local_path, "r") as f:
        config = json.load(f)

    MODEL_CACHE[config_name] = config
    return config


def get_default_feature_config() -> Dict[str, Any]:
    """Get default feature configuration."""
    return {
        "features": [
            "exposure",
            "years_in_business",
            "employee_count",
            "revenue",
            "prior_claims_count",
            "prior_claims_amount",
            "deductible",
            "limit",
            "state_code",
            "industry_code",
        ],
        "categorical_features": ["state_code", "industry_code"],
        "numeric_features": [
            "exposure",
            "years_in_business",
            "employee_count",
            "revenue",
            "prior_claims_count",
            "prior_claims_amount",
            "deductible",
            "limit",
        ],
    }


def prepare_features(
    input_data: Dict[str, Any],
    feature_config: Dict[str, Any],
) -> pd.DataFrame:
    """Prepare feature DataFrame for prediction.

    Args:
        input_data: Input features dict
        feature_config: Feature configuration

    Returns:
        DataFrame with features
    """
    features = feature_config.get("features", [])

    # Create DataFrame with expected features
    df = pd.DataFrame([input_data])

    # Handle missing features
    for feature in features:
        if feature not in df.columns:
            df[feature] = 0

    # Encode categorical features
    categorical = feature_config.get("categorical_features", [])
    for cat in categorical:
        if cat in df.columns:
            # Simple label encoding (in production, use saved encoders)
            df[cat] = pd.Categorical(df[cat]).codes

    # Select only needed features in correct order
    df = df[features]

    return df


class RapidRatePredictor:
    """Predictor for frequency and severity using XGBoost models."""

    def __init__(self, policy_type: str = "GL"):
        """Initialize predictor for a policy type.

        Args:
            policy_type: Policy type code
        """
        self.policy_type = policy_type.upper()
        self.feature_config = load_feature_config(self.policy_type)

        # Model names follow convention: {policy_type}_{model_type}.pkl
        self.freq_model_name = f"{self.policy_type.lower()}_frequency.pkl"
        self.sev_model_name = f"{self.policy_type.lower()}_severity.pkl"

        self._freq_model: Optional[xgb.XGBRegressor] = None
        self._sev_model: Optional[xgb.XGBRegressor] = None

    @property
    def freq_model(self) -> xgb.XGBRegressor:
        """Lazy load frequency model."""
        if self._freq_model is None:
            self._freq_model = load_model(self.freq_model_name)
        return self._freq_model

    @property
    def sev_model(self) -> xgb.XGBRegressor:
        """Lazy load severity model."""
        if self._sev_model is None:
            self._sev_model = load_model(self.sev_model_name)
        return self._sev_model

    def predict_frequency(self, features: Dict[str, Any]) -> float:
        """Predict expected claim frequency.

        Args:
            features: Input features

        Returns:
            Predicted frequency (expected claims per exposure unit)
        """
        df = prepare_features(features, self.feature_config)

        try:
            pred = self.freq_model.predict(df)[0]
            return max(0, float(pred))
        except Exception as e:
            logger.error(f"Frequency prediction error: {e}")
            # Fallback to industry average
            return 0.05  # 5 claims per 100 exposure units

    def predict_severity(self, features: Dict[str, Any]) -> float:
        """Predict expected claim severity.

        Args:
            features: Input features

        Returns:
            Predicted severity (average claim amount)
        """
        df = prepare_features(features, self.feature_config)

        try:
            pred = self.sev_model.predict(df)[0]
            return max(0, float(pred))
        except Exception as e:
            logger.error(f"Severity prediction error: {e}")
            # Fallback to industry average
            return 15000.0

    def predict(self, features: Dict[str, Any]) -> Tuple[float, float]:
        """Predict both frequency and severity.

        Args:
            features: Input features

        Returns:
            Tuple of (frequency, severity)
        """
        freq = self.predict_frequency(features)
        sev = self.predict_severity(features)
        return freq, sev


def get_base_rate(
    policy_type: str,
    state: str,
    industry_code: Optional[str] = None,
) -> float:
    """Get base rate for policy type, state, and industry.

    In production, this would query a rate table.

    Args:
        policy_type: Policy type code
        state: State code
        industry_code: Industry NAICS code

    Returns:
        Base rate per exposure unit
    """
    # Simplified rate table (per $1000 exposure)
    base_rates = {
        "GL": {
            "default": 1.25,
            "CA": 1.45,
            "NY": 1.55,
            "TX": 1.15,
            "FL": 1.35,
        },
        "WC": {
            "default": 2.50,
            "CA": 3.20,
            "NY": 2.80,
            "TX": 2.10,
        },
        "AL": {
            "default": 0.85,
            "CA": 1.05,
            "NY": 1.15,
        },
        "PR": {
            "default": 0.45,
            "FL": 0.85,  # Hurricane prone
            "CA": 0.65,  # Earthquake risk
        },
    }

    policy_rates = base_rates.get(policy_type, {"default": 1.0})
    rate = policy_rates.get(state, policy_rates.get("default", 1.0))

    # Industry modifier (simplified)
    industry_mods = {
        "23": 1.20,  # Construction
        "44": 0.85,  # Retail
        "54": 0.75,  # Professional services
        "62": 1.10,  # Healthcare
        "72": 1.15,  # Hospitality
    }

    if industry_code:
        prefix = industry_code[:2]
        rate *= industry_mods.get(prefix, 1.0)

    return rate
