"""Thrust curve analysis engine."""

import numpy as np
from scipy import integrate, signal
from typing import Dict, List, Tuple
from config import Config


class ThrustAnalyzer:
    """Analyze thrust curve data and compute comprehensive metrics."""

    # Motor classification thresholds (total impulse in N·s)
    MOTOR_CLASSES = [
        ('A', 1.26, 2.5),
        ('B', 2.5, 5.0),
        ('C', 5.0, 10.0),
        ('D', 10.0, 20.0),
        ('E', 20.0, 40.0),
        ('F', 40.0, 80.0),
        ('G', 80.0, 160.0),
        ('H', 160.0, 320.0),
        ('I', 320.0, 640.0),
        ('J', 640.0, 1280.0),
    ]

    def __init__(self, time_data: List[float], force_data: List[float], config: Config = None):
        """
        Initialize analyzer with time-series data.

        Args:
            time_data: Time values in seconds
            force_data: Force values in Newtons
            config: Configuration object (uses default if None)
        """
        self.config = config or Config()
        self.time = np.array(time_data)
        self.force = np.array(force_data)

        # Remove baseline
        self._remove_baseline()

        # Smooth data if configured
        if self.config.SMOOTHING_WINDOW > 1:
            self.force_smooth = self._smooth_data()
        else:
            self.force_smooth = self.force.copy()

    def _remove_baseline(self):
        """Remove baseline by averaging initial readings."""
        baseline_samples = int(self.config.BASELINE_DURATION * self.config.EXPECTED_SAMPLE_RATE)
        if len(self.force) > baseline_samples:
            baseline = np.mean(self.force[:baseline_samples])
            self.force = self.force - baseline
        # Ensure no negative values
        self.force = np.maximum(self.force, 0)

    def _smooth_data(self) -> np.ndarray:
        """Apply Savitzky-Golay filter for smoothing."""
        window = min(self.config.SMOOTHING_WINDOW, len(self.force))
        if window % 2 == 0:  # Must be odd
            window -= 1
        if window < self.config.SMOOTHING_ORDER + 2:
            return self.force.copy()

        try:
            return signal.savgol_filter(self.force, window, self.config.SMOOTHING_ORDER)
        except:
            return self.force.copy()

    def _get_burn_mask(self) -> np.ndarray:
        """Get boolean mask for burn period (above threshold)."""
        threshold = self.peak_thrust() * self.config.BURN_THRESHOLD
        return self.force_smooth > threshold

    def _get_burn_indices(self) -> Tuple[int, int]:
        """Get start and end indices of burn period."""
        mask = self._get_burn_mask()
        if not np.any(mask):
            return 0, 0

        indices = np.where(mask)[0]
        return indices[0], indices[-1]

    def peak_thrust(self) -> float:
        """Maximum thrust value (N)."""
        return float(np.max(self.force_smooth))

    def average_thrust(self) -> float:
        """Average thrust during burn period (N)."""
        mask = self._get_burn_mask()
        if not np.any(mask):
            return 0.0
        return float(np.mean(self.force_smooth[mask]))

    def total_impulse(self) -> float:
        """Total impulse - area under thrust curve (N·s)."""
        return float(integrate.trapezoid(self.force_smooth, self.time))

    def burn_time(self) -> float:
        """Duration of burn above threshold (s)."""
        start_idx, end_idx = self._get_burn_indices()
        if start_idx == end_idx:
            return 0.0
        return float(self.time[end_idx] - self.time[start_idx])

    def time_to_peak(self) -> float:
        """Time from ignition to peak thrust (s)."""
        start_idx, _ = self._get_burn_indices()
        peak_idx = np.argmax(self.force_smooth)
        if start_idx >= len(self.time):
            return 0.0
        return float(self.time[peak_idx] - self.time[start_idx])

    def rise_rate(self) -> float:
        """Average thrust rise rate from ignition to peak (N/s)."""
        start_idx, _ = self._get_burn_indices()
        peak_idx = np.argmax(self.force_smooth)

        if peak_idx <= start_idx:
            return 0.0

        time_diff = self.time[peak_idx] - self.time[start_idx]
        force_diff = self.force_smooth[peak_idx] - self.force_smooth[start_idx]

        if time_diff == 0:
            return 0.0

        return float(force_diff / time_diff)

    def decay_rate(self) -> float:
        """Average thrust decay rate from peak to burnout (N/s)."""
        _, end_idx = self._get_burn_indices()
        peak_idx = np.argmax(self.force_smooth)

        if end_idx <= peak_idx or end_idx >= len(self.time):
            return 0.0

        time_diff = self.time[end_idx] - self.time[peak_idx]
        force_diff = self.force_smooth[end_idx] - self.force_smooth[peak_idx]

        if time_diff == 0:
            return 0.0

        return float(force_diff / time_diff)

    def thrust_stability(self) -> float:
        """Standard deviation of thrust during burn (N)."""
        mask = self._get_burn_mask()
        if not np.any(mask):
            return 0.0
        return float(np.std(self.force_smooth[mask]))

    def motor_class(self) -> str:
        """Motor class letter based on total impulse."""
        impulse = self.total_impulse()

        for letter, min_val, max_val in self.MOTOR_CLASSES:
            if min_val <= impulse < max_val:
                return letter

        # Beyond J class
        if impulse >= 1280.0:
            return 'K+'
        # Below A class
        return '< A'

    def burn_profile(self) -> str:
        """Classify burn profile as progressive, neutral, or regressive."""
        start_idx, end_idx = self._get_burn_indices()
        peak_idx = np.argmax(self.force_smooth)

        if start_idx == end_idx:
            return 'none'

        # Calculate relative position of peak
        burn_duration = end_idx - start_idx
        peak_position = (peak_idx - start_idx) / burn_duration if burn_duration > 0 else 0.5

        if peak_position < 0.3:
            return 'regressive'
        elif peak_position > 0.7:
            return 'progressive'
        else:
            return 'neutral'

    def impulse_efficiency(self) -> float:
        """Ratio of actual impulse to theoretical rectangular impulse."""
        peak = self.peak_thrust()
        burn = self.burn_time()

        if peak == 0 or burn == 0:
            return 0.0

        theoretical_impulse = peak * burn
        actual_impulse = self.total_impulse()

        return float(actual_impulse / theoretical_impulse)

    def time_to_90_percent(self) -> float:
        """Time to reach 90% of peak thrust (s)."""
        start_idx, _ = self._get_burn_indices()
        peak = self.peak_thrust()
        target = 0.9 * peak

        # Find first point above 90% peak
        for i in range(start_idx, len(self.force_smooth)):
            if self.force_smooth[i] >= target:
                return float(self.time[i] - self.time[start_idx])

        return 0.0

    def cato_detection(self) -> bool:
        """Detect catastrophic failure (CATO) based on anomalies."""
        # Check for sudden spike followed by dropout
        if len(self.force_smooth) < 10:
            return False

        # Calculate derivative
        derivative = np.gradient(self.force_smooth)

        # Look for extreme spikes (> 5x std deviation)
        std = np.std(derivative)
        if std > 0:
            spikes = np.abs(derivative) > 5 * std
            if np.sum(spikes) > 2:  # Multiple extreme spikes
                return True

        # Check for premature termination (thrust drops to zero before expected)
        start_idx, end_idx = self._get_burn_indices()
        burn_duration = end_idx - start_idx
        expected_min_duration = 10  # At least 10 samples (0.125s at 80Hz)

        if burn_duration < expected_min_duration and self.peak_thrust() > 10:
            return True

        return False

    def specific_impulse(self, propellant_mass_kg: float = None) -> float:
        """
        Specific impulse if propellant mass is known (s).

        Args:
            propellant_mass_kg: Propellant mass in kilograms

        Returns:
            Specific impulse in seconds, or 0 if mass not provided
        """
        if propellant_mass_kg is None or propellant_mass_kg <= 0:
            return 0.0

        impulse = self.total_impulse()
        weight = propellant_mass_kg * 9.81  # Weight in Newtons
        return float(impulse / weight)

    def compute_all_metrics(self, propellant_mass_kg: float = None) -> Dict:
        """
        Compute all analysis metrics.

        Args:
            propellant_mass_kg: Optional propellant mass for Isp calculation

        Returns:
            Dictionary containing all metrics
        """
        warnings = []

        # Check data quality
        if len(self.time) < 10:
            warnings.append("Insufficient data points for reliable analysis")

        cato = self.cato_detection()
        if cato:
            warnings.append("Possible CATO (catastrophic failure) detected")

        metrics = {
            # Core metrics
            'peak_thrust_n': round(self.peak_thrust(), 2),
            'avg_thrust_n': round(self.average_thrust(), 2),
            'total_impulse_ns': round(self.total_impulse(), 2),
            'burn_time_s': round(self.burn_time(), 3),
            'motor_class': self.motor_class(),

            # Timing metrics
            'time_to_peak_s': round(self.time_to_peak(), 3),
            'time_to_90pct_s': round(self.time_to_90_percent(), 3),

            # Rate metrics
            'rise_rate_ns': round(self.rise_rate(), 2),
            'decay_rate_ns': round(self.decay_rate(), 2),

            # Stability metrics
            'thrust_stability_std': round(self.thrust_stability(), 2),
            'impulse_efficiency': round(self.impulse_efficiency(), 3),

            # Profile classification
            'burn_profile': self.burn_profile(),

            # Anomaly detection
            'cato_detected': cato,

            # Optional metrics
            'specific_impulse_s': round(self.specific_impulse(propellant_mass_kg), 2) if propellant_mass_kg else None,

            # Warnings
            'warnings': warnings
        }

        return metrics
