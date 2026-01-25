"""
Thrust curve simulator for testing without hardware.

Generates realistic rocket motor thrust curves with various profiles.
"""

import numpy as np
import time
import json
from typing import Tuple


class MotorSimulator:
    """Generate realistic motor thrust curves."""

    def __init__(self, peak_thrust: float = 100.0, burn_time: float = 2.0, profile: str = 'neutral'):
        """
        Initialize motor simulator.

        Args:
            peak_thrust: Peak thrust in Newtons
            burn_time: Total burn duration in seconds
            profile: Burn profile type ('progressive', 'neutral', 'regressive')
        """
        self.peak_thrust = peak_thrust
        self.burn_time = burn_time
        self.profile = profile

    def generate_thrust_curve(self, sample_rate: int = 80) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate a complete thrust curve.

        Args:
            sample_rate: Sampling rate in Hz

        Returns:
            Tuple of (time_array, thrust_array)
        """
        num_samples = int(self.burn_time * sample_rate)
        t = np.linspace(0, self.burn_time, num_samples)

        # Startup transient (first 10% of burn time)
        startup_time = self.burn_time * 0.1
        startup = np.clip((t / startup_time) ** 2, 0, 1)

        # Main burn profile
        if self.profile == 'regressive':
            # Peak early, then decay
            burn = 1.0 - 0.4 * (t / self.burn_time)
        elif self.profile == 'progressive':
            # Start low, build to peak
            burn = 0.6 + 0.4 * (t / self.burn_time)
        else:  # neutral
            # Relatively flat
            burn = 1.0 - 0.1 * np.sin(np.pi * t / self.burn_time)

        # Tail-off (last 10% of burn time)
        tailoff_start = self.burn_time * 0.9
        tailoff = np.where(
            t > tailoff_start,
            np.clip(1 - ((t - tailoff_start) / (self.burn_time - tailoff_start)) ** 2, 0, 1),
            1.0
        )

        # Combine phases
        thrust = self.peak_thrust * startup * burn * tailoff

        # Add realistic noise (±2% of peak thrust)
        noise = np.random.normal(0, self.peak_thrust * 0.02, len(t))
        thrust += noise

        # Ensure non-negative
        thrust = np.maximum(thrust, 0)

        return t, thrust

    def generate_cato(self, sample_rate: int = 80) -> Tuple[np.ndarray, np.ndarray]:
        """Generate a CATO (catastrophic failure) thrust curve."""
        normal_time = self.burn_time * 0.3  # Fail at 30% of expected burn
        num_samples = int(normal_time * sample_rate)
        t = np.linspace(0, normal_time, num_samples)

        # Normal startup
        thrust = self.peak_thrust * (t / normal_time)

        # Add noise
        noise = np.random.normal(0, self.peak_thrust * 0.02, len(t))
        thrust += noise

        # Sudden spike at end
        thrust[-5:] *= 2.0

        # Sudden drop to zero
        t = np.append(t, t[-1] + 0.01)
        thrust = np.append(thrust, 0)

        return t, thrust


class WebSocketSimulator:
    """Simulate ESP32 WebSocket client for testing."""

    def __init__(self, server_url: str = 'ws://localhost:5000/esp32'):
        """
        Initialize WebSocket simulator.

        Args:
            server_url: WebSocket server URL
        """
        self.server_url = server_url
        self.motor_sim = None

    def stream_test(self, peak_thrust: float = 50.0, burn_time: float = 2.0,
                   profile: str = 'neutral', sample_rate: int = 80):
        """
        Stream a simulated test to the server.

        Args:
            peak_thrust: Peak thrust in Newtons
            burn_time: Burn duration in seconds
            profile: Burn profile type
            sample_rate: Sampling rate in Hz
        """
        try:
            from websocket import create_connection
        except ImportError:
            print("ERROR: websocket-client library not installed")
            print("Install with: pip install websocket-client")
            return

        # Generate thrust curve
        self.motor_sim = MotorSimulator(peak_thrust, burn_time, profile)
        time_data, thrust_data = self.motor_sim.generate_thrust_curve(sample_rate)

        # Connect to server
        print(f"Connecting to {self.server_url}...")
        ws = create_connection(self.server_url)
        print("Connected!")

        # Stream data
        start_time = time.time()
        sample_interval = 1.0 / sample_rate

        for i, (t, thrust_n) in enumerate(zip(time_data, thrust_data)):
            # Create reading message
            message = {
                'type': 'reading',
                'timestamp': int(t * 1000),  # Convert to milliseconds
                'force': round(thrust_n, 2),
                'raw': int(thrust_n * 1000 + 8388608)  # Fake raw value
            }

            # Send message
            ws.send(json.dumps(message))

            # Maintain timing
            elapsed = time.time() - start_time
            expected_time = (i + 1) * sample_interval
            sleep_time = expected_time - elapsed

            if sleep_time > 0:
                time.sleep(sleep_time)

            # Progress indicator
            if i % sample_rate == 0:
                print(f"Streamed {i}/{len(time_data)} samples ({t:.2f}s)")

        print("Test streaming complete!")
        ws.close()


def main():
    """Run simulator demo."""
    import matplotlib.pyplot as plt

    # Generate different motor profiles
    motors = [
        MotorSimulator(50, 2.0, 'regressive'),
        MotorSimulator(50, 2.0, 'neutral'),
        MotorSimulator(50, 2.0, 'progressive'),
    ]

    profiles = ['Regressive', 'Neutral', 'Progressive']
    colors = ['red', 'blue', 'green']

    plt.figure(figsize=(12, 6))

    for motor, profile, color in zip(motors, profiles, colors):
        t, thrust = motor.generate_thrust_curve()
        plt.plot(t, thrust, label=profile, color=color, linewidth=2)

    plt.xlabel('Time (s)')
    plt.ylabel('Thrust (N)')
    plt.title('Simulated Rocket Motor Thrust Curves')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


if __name__ == '__main__':
    main()
