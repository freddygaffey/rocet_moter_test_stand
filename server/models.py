"""Database models for test data storage."""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from config import Config


class Database:
    """SQLite database manager."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or Config.DATABASE_PATH
        self._ensure_db_directory()
        self._initialize_schema()

    def _ensure_db_directory(self):
        """Create database directory if it doesn't exist."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def _initialize_schema(self):
        """Create database tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Tests table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    label TEXT,
                    duration_ms INTEGER,
                    max_thrust REAL,
                    avg_thrust REAL,
                    total_impulse REAL,
                    motor_class TEXT,
                    data_json TEXT,
                    analysis_json TEXT,
                    crop_start REAL,
                    crop_end REAL
                )
            ''')

            # Add label column if it doesn't exist (for existing databases)
            try:
                cursor.execute('ALTER TABLE tests ADD COLUMN label TEXT')
            except sqlite3.OperationalError:
                pass  # Column already exists

            # Add crop columns if they don't exist (for existing databases)
            try:
                cursor.execute('ALTER TABLE tests ADD COLUMN crop_start REAL')
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute('ALTER TABLE tests ADD COLUMN crop_end REAL')
            except sqlite3.OperationalError:
                pass

            # Calibration table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS calibration (
                    id INTEGER PRIMARY KEY,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    offset INTEGER,
                    scale REAL,
                    points_json TEXT
                )
            ''')

            conn.commit()

    def save_test(self, test_data: Dict, analysis_data: Dict, label: str = None) -> int:
        """Save a test with its analysis results."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO tests (
                    label, duration_ms, max_thrust, avg_thrust, total_impulse,
                    motor_class, data_json, analysis_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                label,
                test_data.get('duration_ms'),
                analysis_data.get('peak_thrust_n'),
                analysis_data.get('avg_thrust_n'),
                analysis_data.get('total_impulse_ns'),
                analysis_data.get('motor_class'),
                json.dumps(test_data),
                json.dumps(analysis_data)
            ))

            conn.commit()
            return cursor.lastrowid

    def get_test(self, test_id: int) -> Optional[Dict]:
        """Retrieve a specific test by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM tests WHERE id = ?', (test_id,))
            row = cursor.fetchone()

            if row:
                return {
                    'id': row['id'],
                    'timestamp': row['timestamp'],
                    'label': row['label'],
                    'duration_ms': row['duration_ms'],
                    'max_thrust': row['max_thrust'],
                    'avg_thrust': row['avg_thrust'],
                    'total_impulse': row['total_impulse'],
                    'motor_class': row['motor_class'],
                    'data': json.loads(row['data_json']) if row['data_json'] else None,
                    'analysis': json.loads(row['analysis_json']) if row['analysis_json'] else None,
                    'crop_start': row['crop_start'],
                    'crop_end': row['crop_end']
                }
            return None

    def get_all_tests(self, limit: int = 100) -> List[Dict]:
        """Retrieve all tests (summary only)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, timestamp, label, duration_ms, max_thrust, avg_thrust,
                       total_impulse, motor_class
                FROM tests
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))

            return [dict(row) for row in cursor.fetchall()]

    def delete_test(self, test_id: int) -> bool:
        """Delete a test by ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM tests WHERE id = ?', (test_id,))
            conn.commit()
            return cursor.rowcount > 0

    def update_test_label(self, test_id: int, label: str) -> bool:
        """Update a test's label."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE tests SET label = ? WHERE id = ?', (label, test_id))
            conn.commit()
            return cursor.rowcount > 0

    def set_crop(self, test_id: int, start_time: float, end_time: float = None) -> bool:
        """Set crop parameters for a test (non-destructive)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE tests SET crop_start = ?, crop_end = ? WHERE id = ?',
                (start_time, end_time, test_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def reset_crop(self, test_id: int) -> bool:
        """Reset crop parameters to view full test data."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE tests SET crop_start = NULL, crop_end = NULL WHERE id = ?',
                (test_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def save_calibration(self, offset: int, scale: float, points: List[Dict]):
        """Save calibration data."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Replace existing calibration (only keep most recent)
            cursor.execute('DELETE FROM calibration')
            cursor.execute('''
                INSERT INTO calibration (id, offset, scale, points_json)
                VALUES (1, ?, ?, ?)
            ''', (offset, scale, json.dumps(points)))

            conn.commit()

    def get_calibration(self) -> Optional[Dict]:
        """Retrieve current calibration data."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM calibration WHERE id = 1')
            row = cursor.fetchone()

            if row:
                return {
                    'timestamp': row['timestamp'],
                    'offset': row['offset'],
                    'scale': row['scale'],
                    'points': json.loads(row['points_json']) if row['points_json'] else []
                }
            return None


class CalibrationManager:
    """Manage calibration data persistence."""

    def __init__(self, db: Database):
        self.db = db
        self.current_calibration = self.db.get_calibration()

    def save(self, offset: int, scale: float, points: List[Dict] = None):
        """Save new calibration."""
        if points is None:
            points = []
        self.db.save_calibration(offset, scale, points)
        self.current_calibration = {
            'timestamp': datetime.now().isoformat(),
            'offset': offset,
            'scale': scale,
            'points': points
        }

    def get(self) -> Optional[Dict]:
        """Get current calibration."""
        return self.current_calibration
