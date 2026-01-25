"""Flask application for rocket motor test stand server."""

from flask import Flask, render_template, jsonify, request, send_file
from flask_socketio import SocketIO
from flask_sock import Sock
from flask_cors import CORS
import os
import json
from datetime import datetime

from config import Config
from models import Database
from websocket_handler import WebSocketHandler

# Initialize Flask app
app = Flask(__name__, static_folder='static', template_folder='static')
app.config.from_object(Config)
CORS(app)

# Initialize SocketIO for dashboard (Socket.IO protocol)
socketio = SocketIO(
    app,
    cors_allowed_origins=app.config['SOCKETIO_CORS_ALLOWED_ORIGINS'],
    async_mode=app.config['SOCKETIO_ASYNC_MODE']
)

# Initialize Sock for ESP32 (plain WebSocket protocol)
sock = Sock(app)

# Initialize database
db = Database()

# Initialize WebSocket handler
ws_handler = WebSocketHandler(socketio, db, Config)


# HTTP Routes

@app.route('/')
def index():
    """Serve the main dashboard page."""
    return send_file('static/index.html')


@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current system status."""
    return jsonify(ws_handler.get_status())


@app.route('/api/tests', methods=['GET'])
def get_tests():
    """Retrieve list of all tests."""
    try:
        limit = request.args.get('limit', 100, type=int)
        tests = db.get_all_tests(limit=limit)
        return jsonify({
            'success': True,
            'tests': tests
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/tests/<int:test_id>', methods=['GET'])
def get_test(test_id):
    """Retrieve specific test details."""
    try:
        test = db.get_test(test_id)
        if test:
            return jsonify({
                'success': True,
                'test': test
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Test not found'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/tests/<int:test_id>', methods=['DELETE'])
def delete_test(test_id):
    """Delete a test."""
    try:
        success = db.delete_test(test_id)
        if success:
            return jsonify({
                'success': True,
                'message': f'Test {test_id} deleted'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Test not found'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/tests/<int:test_id>/label', methods=['PUT'])
def update_test_label(test_id):
    """Update a test's label."""
    try:
        data = request.get_json()
        label = data.get('label', '')

        success = db.update_test_label(test_id, label)
        if success:
            return jsonify({
                'success': True,
                'message': f'Test {test_id} label updated'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Test not found'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/tests/<int:test_id>/csv', methods=['GET'])
def download_test_csv(test_id):
    """Download test data as CSV."""
    try:
        test = db.get_test(test_id)
        if not test:
            return jsonify({
                'success': False,
                'error': 'Test not found'
            }), 404

        # Generate CSV
        csv_lines = ['time_ms,force_n,raw_value\n']

        if test['data'] and 'readings' in test['data']:
            start_time = test['data']['readings'][0]['timestamp']
            for reading in test['data']['readings']:
                time_ms = reading['timestamp'] - start_time
                force_n = reading.get('force', 0)
                raw = reading.get('raw', 0)
                csv_lines.append(f'{time_ms},{force_n},{raw}\n')

        # Write to temp file
        csv_content = ''.join(csv_lines)
        filename = f'test_{test_id}_{test["timestamp"]}.csv'.replace(' ', '_').replace(':', '-')

        return csv_content, 200, {
            'Content-Type': 'text/csv',
            'Content-Disposition': f'attachment; filename={filename}'
        }

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/calibration', methods=['GET', 'POST'])
def calibration():
    """Get or update calibration data."""
    if request.method == 'GET':
        try:
            cal = db.get_calibration()
            return jsonify({
                'success': True,
                'calibration': cal
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    elif request.method == 'POST':
        try:
            data = request.get_json()
            offset = data.get('offset', 0)
            scale = data.get('scale', 1.0)
            points = data.get('points', [])

            db.save_calibration(offset, scale, points)

            return jsonify({
                'success': True,
                'message': 'Calibration saved'
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500


# Plain WebSocket endpoint for ESP32
@sock.route('/esp32')
def esp32_websocket(ws):
    """Handle plain WebSocket connection from ESP32."""
    print("ESP32 connected via plain WebSocket")
    ws_handler.esp32_connected = True
    ws_handler.esp32_ws = ws  # Store reference for sending commands

    # Notify dashboards
    socketio.emit('esp32_status', {'connected': True}, namespace='/dashboard')

    try:
        while True:
            # Receive message from ESP32
            data = ws.receive()
            if data is None:
                break

            # Parse JSON
            try:
                message = json.loads(data)

                # Handle different message types
                if message.get('type') == 'reading':
                    # Add server timestamp
                    message['server_time'] = datetime.now().timestamp()

                    # If recording, buffer the data
                    if ws_handler.recording:
                        ws_handler.test_data.append(message)

                    # Broadcast to all dashboards via Socket.IO
                    socketio.emit('reading', message, namespace='/dashboard')

            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")

    except Exception as e:
        print(f"ESP32 WebSocket error: {e}")
    finally:
        print("ESP32 disconnected")
        ws_handler.esp32_connected = False
        ws_handler.esp32_ws = None  # Clear reference
        socketio.emit('esp32_status', {'connected': False}, namespace='/dashboard')


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500


if __name__ == '__main__':
    print("=" * 60)
    print("Rocket Motor Test Stand Server")
    print("=" * 60)
    print(f"Database: {Config.DATABASE_PATH}")
    print(f"Server starting on http://0.0.0.0:5000")
    print("ESP32 WebSocket: ws://[server-ip]:5000/esp32")
    print("Dashboard WebSocket: ws://[server-ip]:5000/dashboard")
    print("=" * 60)

    # Run with SocketIO
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=True,
        allow_unsafe_werkzeug=True
    )
