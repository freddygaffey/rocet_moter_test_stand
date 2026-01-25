"""WebSocket handler for real-time communication."""

from flask_socketio import SocketIO, emit
from typing import Dict, List
import time
from analysis import ThrustAnalyzer
from models import Database
from config import Config


class WebSocketHandler:
    """Manage WebSocket connections and data flow."""

    def __init__(self, socketio: SocketIO, db: Database, config: Config):
        self.socketio = socketio
        self.db = db
        self.config = config

        # State management
        self.esp32_connected = False
        self.recording = False
        self.test_data = []
        self.test_start_time = None

        # Register handlers
        self._register_handlers()

    def _register_handlers(self):
        """Register all WebSocket event handlers."""

        # ESP32 namespace
        @self.socketio.on('connect', namespace='/esp32')
        def esp32_connect():
            self.esp32_connected = True
            print("ESP32 connected")
            # Notify dashboards
            self.socketio.emit('esp32_status', {'connected': True}, namespace='/dashboard')

        @self.socketio.on('disconnect', namespace='/esp32')
        def esp32_disconnect():
            self.esp32_connected = False
            print("ESP32 disconnected")
            # Notify dashboards
            self.socketio.emit('esp32_status', {'connected': False}, namespace='/dashboard')

        @self.socketio.on('reading', namespace='/esp32')
        def handle_reading(data):
            """Receive sensor reading from ESP32."""
            # Add server timestamp
            data['server_time'] = time.time()

            # If recording, buffer the data
            if self.recording:
                self.test_data.append(data)

            # Broadcast to all dashboards
            self.socketio.emit('reading', data, namespace='/dashboard')

        # Dashboard namespace
        @self.socketio.on('connect', namespace='/dashboard')
        def dashboard_connect():
            print("Dashboard connected")
            # Send current ESP32 status
            emit('esp32_status', {'connected': self.esp32_connected})
            # Send recording status
            emit('recording_status', {'recording': self.recording})

        @self.socketio.on('start_test', namespace='/dashboard')
        def handle_start_test():
            """Start recording test data."""
            if not self.esp32_connected:
                emit('error', {'message': 'ESP32 not connected'})
                return

            self.recording = True
            self.test_data = []
            self.test_start_time = time.time()

            print("Test recording started")

            # Notify all dashboards
            self.socketio.emit('recording_status', {'recording': True}, namespace='/dashboard')

            # Notify ESP32
            self.socketio.emit('command', {'type': 'start_test'}, namespace='/esp32')

        @self.socketio.on('stop_test', namespace='/dashboard')
        def handle_stop_test():
            """Stop recording and analyze data."""
            if not self.recording:
                emit('error', {'message': 'No active recording'})
                return

            self.recording = False
            print(f"Test recording stopped. Data points: {len(self.test_data)}")

            # Notify ESP32
            self.socketio.emit('command', {'type': 'stop_test'}, namespace='/esp32')

            # Process and analyze data
            if len(self.test_data) > 0:
                analysis = self._analyze_test()

                # Save to database
                test_id = self._save_test(analysis)

                # Send results to dashboards
                self.socketio.emit('test_complete', {
                    'test_id': test_id,
                    'analysis': analysis
                }, namespace='/dashboard')
            else:
                emit('error', {'message': 'No data recorded'})

            # Notify recording stopped
            self.socketio.emit('recording_status', {'recording': False}, namespace='/dashboard')

        @self.socketio.on('tare', namespace='/dashboard')
        def handle_tare():
            """Send tare command to ESP32."""
            if not self.esp32_connected:
                emit('error', {'message': 'ESP32 not connected'})
                return

            print("Tare command sent")
            self.socketio.emit('command', {'type': 'tare'}, namespace='/esp32')
            emit('message', {'text': 'Tare command sent'})

        @self.socketio.on('calibrate', namespace='/dashboard')
        def handle_calibrate(data):
            """Send calibration command to ESP32."""
            if not self.esp32_connected:
                emit('error', {'message': 'ESP32 not connected'})
                return

            known_mass = data.get('known_mass')
            if known_mass is None:
                emit('error', {'message': 'Known mass required for calibration'})
                return

            print(f"Calibrate command sent with known mass: {known_mass}g")
            self.socketio.emit('command', {
                'type': 'calibrate',
                'known_mass': known_mass
            }, namespace='/esp32')
            emit('message', {'text': f'Calibration with {known_mass}g sent'})

        @self.socketio.on('get_tests', namespace='/dashboard')
        def handle_get_tests():
            """Retrieve test history."""
            tests = self.db.get_all_tests()
            emit('test_history', {'tests': tests})

        @self.socketio.on('get_test_detail', namespace='/dashboard')
        def handle_get_test_detail(data):
            """Retrieve detailed test data."""
            test_id = data.get('test_id')
            if test_id is None:
                emit('error', {'message': 'Test ID required'})
                return

            test = self.db.get_test(test_id)
            if test:
                emit('test_detail', test)
            else:
                emit('error', {'message': f'Test {test_id} not found'})

    def _analyze_test(self) -> Dict:
        """Analyze recorded test data."""
        # Extract time and force arrays
        time_data = []
        force_data = []

        # Convert timestamps to relative time (seconds)
        start_timestamp = self.test_data[0]['timestamp']

        for reading in self.test_data:
            time_s = (reading['timestamp'] - start_timestamp) / 1000.0  # ms to s
            force_n = reading.get('force', 0)

            time_data.append(time_s)
            force_data.append(force_n)

        # Run analysis
        analyzer = ThrustAnalyzer(time_data, force_data, self.config)
        metrics = analyzer.compute_all_metrics()

        return metrics

    def _save_test(self, analysis: Dict) -> int:
        """Save test data and analysis to database."""
        # Prepare test data summary
        test_data = {
            'timestamp': self.test_start_time,
            'duration_ms': (self.test_data[-1]['timestamp'] - self.test_data[0]['timestamp']) if len(self.test_data) > 0 else 0,
            'data_points': len(self.test_data),
            'readings': self.test_data  # Full data
        }

        # Save to database
        test_id = self.db.save_test(test_data, analysis)

        print(f"Test saved with ID: {test_id}")
        return test_id

    def get_status(self) -> Dict:
        """Get current system status."""
        return {
            'esp32_connected': self.esp32_connected,
            'recording': self.recording,
            'data_points': len(self.test_data) if self.recording else 0
        }
