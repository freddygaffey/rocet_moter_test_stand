"""Configuration for the rocket motor test stand server."""

import os

class Config:
    """Server configuration."""

    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # Database
    DATABASE_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'tests.db')
    CALIBRATION_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'calibration.json')
    TESTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'tests')

    # WebSocket settings
    SOCKETIO_ASYNC_MODE = 'threading'
    SOCKETIO_CORS_ALLOWED_ORIGINS = '*'  # Restrict in production

    # Analysis settings
    BURN_THRESHOLD = 0.05  # 5% of max thrust defines "burn"
    SMOOTHING_WINDOW = 11  # Savitzky-Golay window size
    SMOOTHING_ORDER = 3    # Polynomial order for smoothing
    BASELINE_DURATION = 0.5  # Seconds to average for baseline

    # Sampling
    EXPECTED_SAMPLE_RATE = 80  # Hz
