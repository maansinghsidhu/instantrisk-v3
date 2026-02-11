"""
Monte Carlo Simulation for RapidRate

Implements actuarial loss simulation using:
- Negative Binomial for claim frequency
- Lognormal for claim severity
- Value at Risk (VaR) calculations
"""
import numpy as np
from scipy import stats
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class FrequencyParams:
    """Negative Binomial frequency parameters."""
    mean: float  # Expected number of claims (lambda)
    dispersion: float  # Over-dispersion parameter (r or size)

    def validate(self):
        if self.mean <= 0:
            raise ValueError("Frequency mean must be positive")
        if self.dispersion <= 0:
            raise ValueError("Dispersion parameter must be positive")


@dataclass
class SeverityParams:
    """Lognormal severity parameters."""
    mu: float  # Log-mean
    sigma: float  # Log-standard deviation

    def validate(self):
        if self.sigma <= 0:
            raise ValueError("Severity sigma must be positive")

    @classmethod
    def from_moments(cls, mean: float, cv: float) -> "SeverityParams":
        """Create from mean and coefficient of variation."""
        if mean <= 0:
            raise ValueError("Mean must be positive")
        if cv <= 0:
            raise ValueError("CV must be positive")

        # Convert mean and CV to lognormal parameters
        # CV = sqrt(exp(sigma^2) - 1)
        # So sigma = sqrt(log(CV^2 + 1))
        sigma = np.sqrt(np.log(cv**2 + 1))
        # mu = log(mean) - sigma^2/2
        mu = np.log(mean) - sigma**2 / 2

        return cls(mu=mu, sigma=sigma)


@dataclass
class SimulationResult:
    """Results from Monte Carlo simulation."""
    n_simulations: int
    expected_loss: float
    standard_deviation: float
    var_50: float  # Median
    var_75: float
    var_90: float
    var_95: float
    var_99: float
    tail_var_95: float  # TVaR/CVaR at 95%
    tail_var_99: float
    max_loss: float
    min_loss: float
    loss_free_probability: float
    mean_frequency: float
    mean_severity: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_simulations": self.n_simulations,
            "expected_loss": round(self.expected_loss, 2),
            "standard_deviation": round(self.standard_deviation, 2),
            "var_50": round(self.var_50, 2),
            "var_75": round(self.var_75, 2),
            "var_90": round(self.var_90, 2),
            "var_95": round(self.var_95, 2),
            "var_99": round(self.var_99, 2),
            "tail_var_95": round(self.tail_var_95, 2),
            "tail_var_99": round(self.tail_var_99, 2),
            "max_loss": round(self.max_loss, 2),
            "min_loss": round(self.min_loss, 2),
            "loss_free_probability": round(self.loss_free_probability, 4),
            "mean_frequency": round(self.mean_frequency, 4),
            "mean_severity": round(self.mean_severity, 2),
        }


class MonteCarloSimulator:
    """Monte Carlo loss simulator."""

    def __init__(
        self,
        n_simulations: int = 5000,
        seed: Optional[int] = None,
    ):
        """Initialize simulator.

        Args:
            n_simulations: Number of simulation iterations
            seed: Random seed for reproducibility
        """
        self.n_simulations = n_simulations
        self.rng = np.random.default_rng(seed)

    def simulate_frequency(
        self,
        params: FrequencyParams,
        experience_mod: float = 1.0,
    ) -> np.ndarray:
        """Simulate claim counts using Negative Binomial distribution.

        The Negative Binomial is parameterized as:
        - n (size): dispersion parameter
        - p: probability parameter, computed from mean and dispersion

        Args:
            params: Frequency parameters
            experience_mod: Experience modification factor (multiplier on mean)

        Returns:
            Array of simulated claim counts
        """
        params.validate()

        # Adjust mean by experience mod
        adjusted_mean = params.mean * experience_mod

        # Negative Binomial parameterization
        # Mean = n * (1-p) / p
        # Variance = n * (1-p) / p^2 = Mean / p
        # So p = n / (n + mean)
        n = params.dispersion
        p = n / (n + adjusted_mean)

        # Simulate using scipy
        counts = self.rng.negative_binomial(n=n, p=p, size=self.n_simulations)

        return counts

    def simulate_severity(
        self,
        params: SeverityParams,
        n_claims: int,
        deductible: float = 0,
        limit: Optional[float] = None,
    ) -> np.ndarray:
        """Simulate claim severities using Lognormal distribution.

        Args:
            params: Severity parameters
            n_claims: Number of claims to simulate
            deductible: Per-claim deductible (losses below this are $0)
            limit: Per-claim limit (losses capped at this)

        Returns:
            Array of simulated claim amounts
        """
        params.validate()

        if n_claims == 0:
            return np.array([])

        # Simulate ground-up losses
        severities = self.rng.lognormal(
            mean=params.mu,
            sigma=params.sigma,
            size=n_claims,
        )

        # Apply deductible (excess of loss)
        if deductible > 0:
            severities = np.maximum(severities - deductible, 0)

        # Apply limit
        if limit is not None and limit > 0:
            severities = np.minimum(severities, limit)

        return severities

    def run_simulation(
        self,
        freq_params: FrequencyParams,
        sev_params: SeverityParams,
        experience_mod: float = 1.0,
        deductible: float = 0,
        limit: Optional[float] = None,
    ) -> SimulationResult:
        """Run full Monte Carlo simulation.

        Args:
            freq_params: Frequency distribution parameters
            sev_params: Severity distribution parameters
            experience_mod: Experience modification factor
            deductible: Per-claim deductible
            limit: Per-claim limit

        Returns:
            SimulationResult with all statistics
        """
        # Simulate frequencies
        claim_counts = self.simulate_frequency(freq_params, experience_mod)

        # Simulate aggregate losses
        aggregate_losses = np.zeros(self.n_simulations)
        total_severities = []

        for i, n_claims in enumerate(claim_counts):
            if n_claims > 0:
                severities = self.simulate_severity(
                    sev_params, n_claims, deductible, limit
                )
                aggregate_losses[i] = severities.sum()
                total_severities.extend(severities.tolist())

        # Calculate statistics
        sorted_losses = np.sort(aggregate_losses)

        # VaR percentiles
        var_50 = np.percentile(sorted_losses, 50)
        var_75 = np.percentile(sorted_losses, 75)
        var_90 = np.percentile(sorted_losses, 90)
        var_95 = np.percentile(sorted_losses, 95)
        var_99 = np.percentile(sorted_losses, 99)

        # Tail VaR (Conditional VaR / Expected Shortfall)
        tail_var_95 = sorted_losses[sorted_losses >= var_95].mean() if any(sorted_losses >= var_95) else var_95
        tail_var_99 = sorted_losses[sorted_losses >= var_99].mean() if any(sorted_losses >= var_99) else var_99

        # Mean severity (excluding zero-loss scenarios)
        mean_sev = np.mean(total_severities) if total_severities else 0

        return SimulationResult(
            n_simulations=self.n_simulations,
            expected_loss=aggregate_losses.mean(),
            standard_deviation=aggregate_losses.std(),
            var_50=var_50,
            var_75=var_75,
            var_90=var_90,
            var_95=var_95,
            var_99=var_99,
            tail_var_95=tail_var_95,
            tail_var_99=tail_var_99,
            max_loss=aggregate_losses.max(),
            min_loss=aggregate_losses.min(),
            loss_free_probability=(claim_counts == 0).mean(),
            mean_frequency=claim_counts.mean(),
            mean_severity=mean_sev,
        )


def calculate_experience_mod(
    actual_losses: float,
    expected_losses: float,
    credibility: float = 1.0,
    min_mod: float = 0.5,
    max_mod: float = 2.0,
) -> float:
    """Calculate experience modification factor.

    Args:
        actual_losses: Insured's actual loss experience
        expected_losses: Expected losses for this class
        credibility: Credibility factor (0 to 1)
        min_mod: Minimum allowed mod factor
        max_mod: Maximum allowed mod factor

    Returns:
        Experience modification factor
    """
    if expected_losses <= 0:
        return 1.0

    # Basic mod calculation
    raw_mod = actual_losses / expected_losses

    # Apply credibility weighting
    # Credibility-weighted mod = Z * actual_ratio + (1-Z) * 1.0
    weighted_mod = credibility * raw_mod + (1 - credibility) * 1.0

    # Apply bounds
    return max(min_mod, min(max_mod, weighted_mod))


def calculate_credibility(
    years_of_experience: int,
    premium_volume: float,
    full_credibility_premium: float = 500000,
    full_credibility_years: int = 5,
) -> float:
    """Calculate credibility factor based on experience volume.

    Args:
        years_of_experience: Years of loss history
        premium_volume: Annual premium volume
        full_credibility_premium: Premium volume for full credibility
        full_credibility_years: Years needed for full credibility

    Returns:
        Credibility factor (0 to 1)
    """
    # Square root rule for credibility
    volume_cred = min(1.0, np.sqrt(premium_volume / full_credibility_premium))
    years_cred = min(1.0, years_of_experience / full_credibility_years)

    # Combined credibility (geometric mean)
    return np.sqrt(volume_cred * years_cred)


def estimate_parameters_from_history(
    claim_counts: list,
    claim_amounts: list,
) -> Tuple[FrequencyParams, SeverityParams]:
    """Estimate distribution parameters from historical data.

    Args:
        claim_counts: List of annual claim counts
        claim_amounts: List of individual claim amounts

    Returns:
        Tuple of (FrequencyParams, SeverityParams)
    """
    # Frequency: fit Negative Binomial
    counts = np.array(claim_counts)
    mean_freq = counts.mean()
    var_freq = counts.var()

    # Estimate dispersion (method of moments)
    # Var = mean + mean^2/r, so r = mean^2 / (var - mean)
    if var_freq > mean_freq:
        dispersion = mean_freq**2 / (var_freq - mean_freq)
    else:
        dispersion = 10.0  # Default if variance <= mean (Poisson-like)

    freq_params = FrequencyParams(mean=mean_freq, dispersion=dispersion)

    # Severity: fit Lognormal
    amounts = np.array([a for a in claim_amounts if a > 0])
    if len(amounts) > 0:
        log_amounts = np.log(amounts)
        mu = log_amounts.mean()
        sigma = log_amounts.std()
        if sigma <= 0:
            sigma = 0.5  # Default
        sev_params = SeverityParams(mu=mu, sigma=sigma)
    else:
        # Default parameters
        sev_params = SeverityParams(mu=np.log(10000), sigma=1.0)

    return freq_params, sev_params
