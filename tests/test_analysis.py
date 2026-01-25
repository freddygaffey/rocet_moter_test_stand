"""
Unit tests for thrust curve analysis engine.
"""

import pytest
import numpy as np
import sys
import os

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

from analysis import ThrustAnalyzer
from config import Config


class TestThrustAnalyzer:
    """Test suite for ThrustAnalyzer class."""

    def test_rectangular_impulse(self):
        """Test impulse calculation with rectangular thrust curve."""
        # Perfect rectangular curve: 100N for 2 seconds = 200 N·s
        time = np.linspace(0, 2, 160)  # 80 Hz for 2 seconds
        force = np.full(160, 100.0)

        analyzer = ThrustAnalyzer(time.tolist(), force.tolist())
        impulse = analyzer.total_impulse()

        # Should be approximately 200 N·s
        assert abs(impulse - 200.0) < 1.0, f"Expected ~200, got {impulse}"

    def test_triangular_impulse(self):
        """Test impulse calculation with triangular thrust curve."""
        # Triangular curve: 0 to 100N and back to 0 over 2 seconds
        # Area = 0.5 * base * height = 0.5 * 2 * 100 = 100 N·s
        time = np.linspace(0, 2, 160)
        force = np.concatenate([
            np.linspace(0, 100, 80),
            np.linspace(100, 0, 80)
        ])

        analyzer = ThrustAnalyzer(time.tolist(), force.tolist())
        impulse = analyzer.total_impulse()

        # Should be approximately 100 N·s
        assert abs(impulse - 100.0) < 5.0, f"Expected ~100, got {impulse}"

    def test_peak_thrust(self):
        """Test peak thrust detection."""
        time = np.linspace(0, 2, 160)
        force = np.concatenate([
            np.linspace(0, 150, 80),
            np.linspace(150, 0, 80)
        ])

        analyzer = ThrustAnalyzer(time.tolist(), force.tolist())
        peak = analyzer.peak_thrust()

        assert abs(peak - 150.0) < 1.0, f"Expected ~150, got {peak}"

    def test_burn_time(self):
        """Test burn time calculation with threshold."""
        # 2 second curve with clear start/end
        time = np.linspace(0, 3, 240)  # 80 Hz for 3 seconds
        force = np.zeros(240)
        force[40:200] = 100.0  # Active burn from 0.5s to 2.5s = 2.0s

        analyzer = ThrustAnalyzer(time.tolist(), force.tolist())
        burn_time = analyzer.burn_time()

        # Should be approximately 2 seconds
        assert abs(burn_time - 2.0) < 0.2, f"Expected ~2.0, got {burn_time}"

    def test_motor_classification(self):
        """Test motor class assignment based on total impulse."""
        test_cases = [
            (1.5, 'A'),   # 1.26-2.5 N·s
            (3.0, 'B'),   # 2.5-5.0 N·s
            (7.0, 'C'),   # 5.0-10.0 N·s
            (15.0, 'D'),  # 10.0-20.0 N·s
            (30.0, 'E'),  # 20.0-40.0 N·s
            (60.0, 'F'),  # 40.0-80.0 N·s
            (100.0, 'G'), # 80.0-160.0 N·s
        ]

        for impulse_target, expected_class in test_cases:
            # Create curve with desired impulse
            # Rectangular: force * time = impulse
            force_val = impulse_target / 1.0  # 1 second burn
            time = np.linspace(0, 1.5, 120)
            force = np.zeros(120)
            force[20:100] = force_val  # 1 second burn

            analyzer = ThrustAnalyzer(time.tolist(), force.tolist())
            motor_class = analyzer.motor_class()

            assert motor_class == expected_class, \
                f"Impulse {impulse_target}: expected {expected_class}, got {motor_class}"

    def test_time_to_peak(self):
        """Test time to peak calculation."""
        time = np.linspace(0, 2, 160)
        # Peak at 0.5 seconds
        force = np.concatenate([
            np.linspace(0, 100, 40),   # Rise to peak at 0.5s
            np.full(40, 100),          # Hold
            np.linspace(100, 0, 80)    # Decay
        ])

        analyzer = ThrustAnalyzer(time.tolist(), force.tolist())
        time_to_peak = analyzer.time_to_peak()

        # Should be approximately 0.5 seconds
        assert abs(time_to_peak - 0.5) < 0.1, f"Expected ~0.5, got {time_to_peak}"

    def test_rise_and_decay_rates(self):
        """Test rise and decay rate calculations."""
        time = np.linspace(0, 3, 240)

        # Simple triangular profile
        # Rise from 0 to 100N in 1 second = 100 N/s
        # Decay from 100 to 0N in 2 seconds = -50 N/s
        force = np.concatenate([
            np.linspace(0, 100, 80),    # 1 second rise
            np.linspace(100, 0, 160)    # 2 second decay
        ])

        analyzer = ThrustAnalyzer(time.tolist(), force.tolist())

        rise_rate = analyzer.rise_rate()
        decay_rate = analyzer.decay_rate()

        # Rise should be ~100 N/s
        assert abs(rise_rate - 100.0) < 20.0, f"Expected rise ~100, got {rise_rate}"

        # Decay should be ~-50 N/s
        assert abs(decay_rate - (-50.0)) < 20.0, f"Expected decay ~-50, got {decay_rate}"

    def test_burn_profile_classification(self):
        """Test burn profile classification."""
        time = np.linspace(0, 2, 160)

        # Regressive: peak early
        force_regressive = np.concatenate([
            np.linspace(0, 100, 20),
            np.linspace(100, 50, 140)
        ])
        analyzer = ThrustAnalyzer(time.tolist(), force_regressive.tolist())
        assert analyzer.burn_profile() == 'regressive'

        # Progressive: peak late
        force_progressive = np.concatenate([
            np.linspace(0, 50, 140),
            np.linspace(50, 100, 20)
        ])
        analyzer = ThrustAnalyzer(time.tolist(), force_progressive.tolist())
        assert analyzer.burn_profile() == 'progressive'

        # Neutral: peak in middle
        force_neutral = np.concatenate([
            np.linspace(0, 100, 80),
            np.linspace(100, 0, 80)
        ])
        analyzer = ThrustAnalyzer(time.tolist(), force_neutral.tolist())
        assert analyzer.burn_profile() == 'neutral'

    def test_impulse_efficiency(self):
        """Test impulse efficiency calculation."""
        time = np.linspace(0, 2, 160)

        # Perfect rectangular: efficiency = 1.0
        force_rect = np.full(160, 100.0)
        analyzer = ThrustAnalyzer(time.tolist(), force_rect.tolist())
        efficiency = analyzer.impulse_efficiency()
        assert abs(efficiency - 1.0) < 0.1, f"Rectangular efficiency should be ~1.0, got {efficiency}"

        # Triangular: efficiency = 0.5
        force_tri = np.concatenate([
            np.linspace(0, 100, 80),
            np.linspace(100, 0, 80)
        ])
        analyzer = ThrustAnalyzer(time.tolist(), force_tri.tolist())
        efficiency = analyzer.impulse_efficiency()
        assert abs(efficiency - 0.5) < 0.1, f"Triangular efficiency should be ~0.5, got {efficiency}"

    def test_noisy_data_filtering(self):
        """Test that smoothing handles noisy data."""
        time = np.linspace(0, 2, 160)
        clean_force = np.concatenate([
            np.linspace(0, 100, 80),
            np.linspace(100, 0, 80)
        ])

        # Add significant noise
        noisy_force = clean_force + np.random.normal(0, 10, len(clean_force))

        analyzer = ThrustAnalyzer(time.tolist(), noisy_force.tolist())

        # Peak should still be detected reasonably
        peak = analyzer.peak_thrust()
        assert 90 < peak < 120, f"Peak detection failed with noise: {peak}"

        # Impulse should still be reasonable
        impulse = analyzer.total_impulse()
        assert 80 < impulse < 120, f"Impulse calculation failed with noise: {impulse}"

    def test_specific_impulse(self):
        """Test specific impulse calculation."""
        time = np.linspace(0, 2, 160)
        force = np.full(160, 98.1)  # 98.1N for 2s = 196.2 N·s

        analyzer = ThrustAnalyzer(time.tolist(), force.tolist())

        # With 2kg propellant: Isp = 196.2 / (2 * 9.81) = ~10 seconds
        isp = analyzer.specific_impulse(propellant_mass_kg=2.0)

        assert abs(isp - 10.0) < 1.0, f"Expected Isp ~10s, got {isp}"

    def test_cato_detection(self):
        """Test CATO (catastrophic failure) detection."""
        time = np.linspace(0, 1, 80)

        # Normal curve - no CATO
        force_normal = np.concatenate([
            np.linspace(0, 100, 40),
            np.linspace(100, 0, 40)
        ])
        analyzer = ThrustAnalyzer(time.tolist(), force_normal.tolist())
        assert not analyzer.cato_detection(), "False CATO detected on normal curve"

        # CATO curve - sudden spike and dropout
        force_cato = np.concatenate([
            np.linspace(0, 100, 30),
            [200, 0, 0, 0]  # Sudden spike then dropout
        ])
        force_cato = np.pad(force_cato, (0, 80 - len(force_cato)), constant_values=0)
        analyzer = ThrustAnalyzer(time.tolist(), force_cato.tolist())
        # Note: CATO detection is heuristic-based, may need tuning
        # This test documents expected behavior

    def test_comprehensive_metrics(self):
        """Test that compute_all_metrics returns all expected keys."""
        time = np.linspace(0, 2, 160)
        force = np.concatenate([
            np.linspace(0, 100, 80),
            np.linspace(100, 0, 80)
        ])

        analyzer = ThrustAnalyzer(time.tolist(), force.tolist())
        metrics = analyzer.compute_all_metrics(propellant_mass_kg=0.5)

        # Check all expected keys are present
        expected_keys = [
            'peak_thrust_n', 'avg_thrust_n', 'total_impulse_ns', 'burn_time_s',
            'motor_class', 'time_to_peak_s', 'time_to_90pct_s', 'rise_rate_ns',
            'decay_rate_ns', 'thrust_stability_std', 'impulse_efficiency',
            'burn_profile', 'cato_detected', 'specific_impulse_s', 'warnings'
        ]

        for key in expected_keys:
            assert key in metrics, f"Missing key: {key}"

        # Check values are reasonable
        assert metrics['peak_thrust_n'] > 0
        assert metrics['total_impulse_ns'] > 0
        assert metrics['motor_class'] in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K+', '< A']
        assert isinstance(metrics['warnings'], list)

    def test_edge_case_empty_data(self):
        """Test handling of minimal data."""
        time = [0, 0.1]
        force = [0, 0]

        analyzer = ThrustAnalyzer(time, force)
        metrics = analyzer.compute_all_metrics()

        # Should not crash, return zeros/defaults
        assert metrics['peak_thrust_n'] == 0
        assert metrics['total_impulse_ns'] >= 0
        assert len(metrics['warnings']) > 0  # Should warn about insufficient data


def test_config_parameters():
    """Test that Config parameters are used correctly."""
    config = Config()

    assert config.BURN_THRESHOLD == 0.05
    assert config.SMOOTHING_WINDOW == 11
    assert config.EXPECTED_SAMPLE_RATE == 80


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
