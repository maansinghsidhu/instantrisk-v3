"""
RapidRate Lambda Handler

Provides actuarial pricing via Monte Carlo simulation.
Supports predict, simulate, and price actions.
"""
import json
import logging
from typing import Dict, Any, Optional

from monte_carlo import (
    MonteCarloSimulator,
    FrequencyParams,
    SeverityParams,
    SimulationResult,
    calculate_experience_mod,
    calculate_credibility,
    estimate_parameters_from_history,
)
from models import RapidRatePredictor, get_base_rate

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main Lambda handler.

    Supports three actions:
    - predict: Get frequency/severity predictions from XGBoost models
    - simulate: Run Monte Carlo simulation
    - price: Full pricing with premium calculation

    Args:
        event: Lambda event with action and parameters
        context: Lambda context

    Returns:
        Response with results or error
    """
    try:
        # Handle API Gateway proxy format
        if "body" in event:
            body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
        else:
            body = event

        action = body.get("action", "price")
        logger.info(f"Processing action: {action}")

        if action == "predict":
            return handle_predict(body)
        elif action == "simulate":
            return handle_simulate(body)
        elif action == "price":
            return handle_price(body)
        else:
            return error_response(400, f"Unknown action: {action}")

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return error_response(400, str(e))
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return error_response(500, f"Internal error: {str(e)}")


def handle_predict(body: Dict[str, Any]) -> Dict[str, Any]:
    """Handle predict action.

    Uses XGBoost models to predict frequency and severity.

    Args:
        body: Request body with features

    Returns:
        Response with predictions
    """
    policy_type = body.get("policy_type", "GL")
    features = body.get("features", {})

    if not features:
        return error_response(400, "Features are required")

    predictor = RapidRatePredictor(policy_type)
    frequency, severity = predictor.predict(features)

    return success_response({
        "policy_type": policy_type,
        "predicted_frequency": frequency,
        "predicted_severity": severity,
        "expected_loss": frequency * severity,
    })


def handle_simulate(body: Dict[str, Any]) -> Dict[str, Any]:
    """Handle simulate action.

    Runs Monte Carlo simulation with provided or predicted parameters.

    Args:
        body: Request body with simulation parameters

    Returns:
        Response with simulation results
    """
    # Get simulation parameters
    n_simulations = body.get("n_simulations", 5000)
    seed = body.get("seed")

    # Frequency parameters
    freq_mean = body.get("frequency_mean")
    freq_dispersion = body.get("frequency_dispersion", 2.0)

    # Severity parameters
    sev_mean = body.get("severity_mean")
    sev_cv = body.get("severity_cv", 1.5)  # Coefficient of variation
    sev_mu = body.get("severity_mu")
    sev_sigma = body.get("severity_sigma")

    # Policy terms
    deductible = body.get("deductible", 0)
    limit = body.get("limit")
    experience_mod = body.get("experience_mod", 1.0)

    # Validate and set up parameters
    if freq_mean is None:
        # Try to predict from features
        policy_type = body.get("policy_type", "GL")
        features = body.get("features", {})
        if features:
            predictor = RapidRatePredictor(policy_type)
            freq_mean, sev_mean_pred = predictor.predict(features)
            if sev_mean is None:
                sev_mean = sev_mean_pred
        else:
            return error_response(400, "Either frequency_mean or features are required")

    # Build severity params
    if sev_mu is not None and sev_sigma is not None:
        sev_params = SeverityParams(mu=sev_mu, sigma=sev_sigma)
    elif sev_mean is not None:
        sev_params = SeverityParams.from_moments(mean=sev_mean, cv=sev_cv)
    else:
        return error_response(400, "Severity parameters required (mean+cv or mu+sigma)")

    freq_params = FrequencyParams(mean=freq_mean, dispersion=freq_dispersion)

    # Handle insured loss history for experience mod
    insured_history = body.get("insured_loss_history")
    if insured_history and experience_mod == 1.0:
        # Calculate experience mod from history
        actual_losses = sum(insured_history.get("claim_amounts", []))
        expected_losses = freq_mean * sev_params.mu * len(insured_history.get("years", [1]))

        years_exp = len(insured_history.get("years", []))
        premium = body.get("premium_volume", 100000)
        credibility = calculate_credibility(years_exp, premium)

        experience_mod = calculate_experience_mod(
            actual_losses=actual_losses,
            expected_losses=expected_losses,
            credibility=credibility,
        )

    # Run simulation
    simulator = MonteCarloSimulator(n_simulations=n_simulations, seed=seed)
    result = simulator.run_simulation(
        freq_params=freq_params,
        sev_params=sev_params,
        experience_mod=experience_mod,
        deductible=deductible,
        limit=limit,
    )

    response_data = result.to_dict()
    response_data["experience_mod"] = experience_mod
    response_data["deductible"] = deductible
    response_data["limit"] = limit

    return success_response(response_data)


def handle_price(body: Dict[str, Any]) -> Dict[str, Any]:
    """Handle price action.

    Full pricing workflow including prediction, simulation, and premium calculation.

    Args:
        body: Request body with policy details

    Returns:
        Response with pricing results
    """
    # Required fields
    policy_type = body.get("policy_type", "GL")
    state = body.get("state", "CA")
    exposure = body.get("exposure", 1000000)  # e.g., revenue, payroll
    features = body.get("features", {})

    # Optional
    deductible = body.get("deductible", 0)
    limit = body.get("limit")
    industry_code = body.get("industry_code")
    insured_history = body.get("insured_loss_history")
    n_simulations = body.get("n_simulations", 5000)

    # Ensure features include required fields
    features["exposure"] = exposure
    features["deductible"] = deductible
    features["limit"] = limit or 1000000
    features["state_code"] = state
    if industry_code:
        features["industry_code"] = industry_code

    # Step 1: Predict frequency and severity
    predictor = RapidRatePredictor(policy_type)
    freq_rate, sev_mean = predictor.predict(features)

    # Scale frequency by exposure
    # freq_rate is per exposure unit, scale to actual exposure
    exposure_units = exposure / 1000  # Assuming rate is per $1000
    freq_mean = freq_rate * exposure_units

    # Step 2: Calculate experience mod if history provided
    experience_mod = 1.0
    credibility = 0.0

    if insured_history:
        claim_counts = insured_history.get("claim_counts", [])
        claim_amounts = insured_history.get("claim_amounts", [])
        years = insured_history.get("years", [])
        premium_volume = insured_history.get("premium_volume", exposure * 0.01)

        if claim_counts and len(years) > 0:
            # Calculate expected vs actual
            expected_freq = freq_rate * len(years)
            actual_freq = sum(claim_counts) / len(years) if years else 0

            expected_sev = sev_mean
            actual_sev = sum(claim_amounts) / sum(claim_counts) if sum(claim_counts) > 0 else sev_mean

            expected_loss = expected_freq * expected_sev * len(years)
            actual_loss = sum(claim_amounts)

            credibility = calculate_credibility(
                years_of_experience=len(years),
                premium_volume=premium_volume,
            )

            experience_mod = calculate_experience_mod(
                actual_losses=actual_loss,
                expected_losses=expected_loss,
                credibility=credibility,
            )

    # Step 3: Run Monte Carlo simulation
    freq_params = FrequencyParams(mean=freq_mean, dispersion=2.0)
    sev_params = SeverityParams.from_moments(mean=sev_mean, cv=1.5)

    simulator = MonteCarloSimulator(n_simulations=n_simulations)
    sim_result = simulator.run_simulation(
        freq_params=freq_params,
        sev_params=sev_params,
        experience_mod=experience_mod,
        deductible=deductible,
        limit=limit,
    )

    # Step 4: Calculate premium
    base_rate = get_base_rate(policy_type, state, industry_code)
    expected_loss = sim_result.expected_loss

    # Premium components
    loss_cost = expected_loss
    expense_load = 0.25  # 25% expense ratio
    profit_margin = 0.05  # 5% profit margin
    risk_load = (sim_result.var_95 - expected_loss) * 0.10  # 10% of tail risk

    # Indicated premium
    indicated_premium = (loss_cost + risk_load) / (1 - expense_load - profit_margin)

    # Apply experience mod to final premium
    modified_premium = indicated_premium * experience_mod

    # Premium range (based on simulation uncertainty)
    premium_low = modified_premium * 0.85
    premium_high = modified_premium * 1.15

    return success_response({
        "policy_type": policy_type,
        "state": state,
        "exposure": exposure,

        # Predictions
        "predicted_frequency_rate": freq_rate,
        "predicted_severity": sev_mean,
        "scaled_frequency": freq_mean,

        # Experience rating
        "experience_mod": round(experience_mod, 3),
        "credibility": round(credibility, 3),

        # Simulation results
        "simulation": sim_result.to_dict(),

        # Pricing
        "base_rate": round(base_rate, 4),
        "loss_cost": round(loss_cost, 2),
        "risk_load": round(risk_load, 2),
        "expense_load_pct": expense_load,
        "profit_margin_pct": profit_margin,

        "indicated_premium": round(indicated_premium, 2),
        "modified_premium": round(modified_premium, 2),
        "premium_range": {
            "low": round(premium_low, 2),
            "high": round(premium_high, 2),
        },

        # Policy terms
        "deductible": deductible,
        "limit": limit,
    })


def success_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Format success response."""
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps({"success": True, "data": data}),
    }


def error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Format error response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps({"success": False, "error": message}),
    }
