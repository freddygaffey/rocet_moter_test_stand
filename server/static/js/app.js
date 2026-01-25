/**
 * Main application controller for rocket motor test stand dashboard
 */

class TestStandApp {
    constructor() {
        // WebSocket connection
        this.socket = null;
        this.serverConnected = false;
        this.esp32Connected = false;

        // Test state
        this.recording = false;
        this.testData = [];
        this.testStartTime = null;
        this.currentTestId = null;

        // Live stats
        this.peakThrust = 0;
        this.currentImpulse = 0;

        // Chart
        this.chart = new ThrustChart('thrust-chart');

        // Initialize
        this.initializeUI();
        this.connectWebSocket();
        this.loadTestHistory();
    }

    initializeUI() {
        // Get UI elements
        this.elements = {
            serverStatus: document.getElementById('server-status'),
            esp32Status: document.getElementById('esp32-status'),
            recordingStatus: document.getElementById('recording-status'),

            currentThrust: document.getElementById('current-thrust'),
            peakThrustDisplay: document.getElementById('peak-thrust'),
            testDuration: document.getElementById('test-duration'),
            currentImpulse: document.getElementById('current-impulse'),

            btnStartTest: document.getElementById('btn-start-test'),
            btnStopTest: document.getElementById('btn-stop-test'),
            btnTare: document.getElementById('btn-tare'),
            btnCalibrate: document.getElementById('btn-calibrate'),

            analysisSection: document.getElementById('analysis-section'),
            analysisContent: document.getElementById('analysis-content'),
            btnDownloadCSV: document.getElementById('btn-download-csv'),

            btnRefreshHistory: document.getElementById('btn-refresh-history'),
            historyTbody: document.getElementById('history-tbody'),

            calibrateModal: document.getElementById('calibrate-modal'),
            knownMassInput: document.getElementById('known-mass-input'),
            btnCalibrateConfirm: document.getElementById('btn-calibrate-confirm'),
            btnCalibrateCancel: document.getElementById('btn-calibrate-cancel'),
        };

        // Attach event listeners
        this.elements.btnStartTest.addEventListener('click', () => this.startTest());
        this.elements.btnStopTest.addEventListener('click', () => this.stopTest());
        this.elements.btnTare.addEventListener('click', () => this.tare());
        this.elements.btnCalibrate.addEventListener('click', () => this.showCalibrateModal());

        this.elements.btnRefreshHistory.addEventListener('click', () => this.loadTestHistory());
        this.elements.btnDownloadCSV.addEventListener('click', () => this.downloadCSV());

        this.elements.btnCalibrateConfirm.addEventListener('click', () => this.calibrate());
        this.elements.btnCalibrateCancel.addEventListener('click', () => this.hideCalibrateModal());
    }

    connectWebSocket() {
        console.log('Connecting to WebSocket server...');

        this.socket = io('/dashboard');

        this.socket.on('connect', () => {
            console.log('WebSocket connected');
            this.serverConnected = true;
            this.updateStatusIndicators();
        });

        this.socket.on('disconnect', () => {
            console.log('WebSocket disconnected');
            this.serverConnected = false;
            this.esp32Connected = false;
            this.updateStatusIndicators();
        });

        this.socket.on('esp32_status', (data) => {
            console.log('ESP32 status:', data);
            this.esp32Connected = data.connected;
            this.updateStatusIndicators();
        });

        this.socket.on('recording_status', (data) => {
            console.log('Recording status:', data);
            this.recording = data.recording;
            this.updateStatusIndicators();

            if (this.recording) {
                this.onTestStarted();
            }
        });

        this.socket.on('reading', (data) => {
            this.handleReading(data);
        });

        this.socket.on('test_complete', (data) => {
            console.log('Test complete:', data);
            this.onTestComplete(data);
        });

        this.socket.on('error', (data) => {
            console.error('Server error:', data);
            alert('Error: ' + data.message);
        });

        this.socket.on('message', (data) => {
            console.log('Server message:', data);
        });

        this.socket.on('test_history', (data) => {
            this.displayTestHistory(data.tests);
        });

        this.socket.on('test_detail', (data) => {
            this.displayTestDetail(data);
        });
    }

    updateStatusIndicators() {
        // Server status
        if (this.serverConnected) {
            this.elements.serverStatus.textContent = 'Connected';
            this.elements.serverStatus.className = 'status-indicator connected';
        } else {
            this.elements.serverStatus.textContent = 'Disconnected';
            this.elements.serverStatus.className = 'status-indicator disconnected';
        }

        // ESP32 status
        if (this.esp32Connected) {
            this.elements.esp32Status.textContent = 'Online';
            this.elements.esp32Status.className = 'status-indicator connected';
        } else {
            this.elements.esp32Status.textContent = 'Offline';
            this.elements.esp32Status.className = 'status-indicator disconnected';
        }

        // Recording status
        if (this.recording) {
            this.elements.recordingStatus.textContent = 'Recording';
            this.elements.recordingStatus.className = 'status-indicator recording';
        } else {
            this.elements.recordingStatus.textContent = 'Idle';
            this.elements.recordingStatus.className = 'status-indicator idle';
        }

        // Update button states
        const canControl = this.serverConnected && this.esp32Connected;

        this.elements.btnStartTest.disabled = !canControl || this.recording;
        this.elements.btnStopTest.disabled = !canControl || !this.recording;
        this.elements.btnTare.disabled = !canControl || this.recording;
        this.elements.btnCalibrate.disabled = !canControl || this.recording;
    }

    handleReading(data) {
        const time_s = (data.timestamp - (this.testStartTime || data.timestamp)) / 1000.0;
        const force_n = data.force;

        // Update chart
        if (this.recording) {
            this.chart.addPoint(time_s, force_n);

            // Store data
            this.testData.push({ time: time_s, force: force_n, timestamp: data.timestamp, raw: data.raw });

            // Update live stats
            this.elements.currentThrust.textContent = force_n.toFixed(2);

            if (force_n > this.peakThrust) {
                this.peakThrust = force_n;
                this.elements.peakThrustDisplay.textContent = this.peakThrust.toFixed(2);
            }

            // Update duration
            this.elements.testDuration.textContent = time_s.toFixed(2);

            // Approximate impulse (trapezoidal integration)
            if (this.testData.length > 1) {
                const prev = this.testData[this.testData.length - 2];
                const dt = time_s - prev.time;
                const avgForce = (force_n + prev.force) / 2;
                this.currentImpulse += avgForce * dt;
                this.elements.currentImpulse.textContent = this.currentImpulse.toFixed(2);
            }
        }
    }

    startTest() {
        console.log('Starting test...');
        this.socket.emit('start_test');
    }

    stopTest() {
        console.log('Stopping test...');
        this.socket.emit('stop_test');
    }

    tare() {
        console.log('Taring...');
        this.socket.emit('tare');
    }

    showCalibrateModal() {
        this.elements.calibrateModal.classList.add('show');
        this.elements.knownMassInput.value = '';
        this.elements.knownMassInput.focus();
    }

    hideCalibrateModal() {
        this.elements.calibrateModal.classList.remove('show');
    }

    calibrate() {
        const knownMass = parseFloat(this.elements.knownMassInput.value);

        if (isNaN(knownMass) || knownMass <= 0) {
            alert('Please enter a valid mass value greater than 0');
            return;
        }

        console.log('Calibrating with known mass:', knownMass);
        this.socket.emit('calibrate', { known_mass: knownMass });

        this.hideCalibrateModal();
    }

    onTestStarted() {
        // Reset test data
        this.testData = [];
        this.testStartTime = Date.now();
        this.peakThrust = 0;
        this.currentImpulse = 0;

        // Clear chart
        this.chart.clear();

        // Reset live stats
        this.elements.currentThrust.textContent = '0.00';
        this.elements.peakThrustDisplay.textContent = '0.00';
        this.elements.testDuration.textContent = '0.00';
        this.elements.currentImpulse.textContent = '0.00';

        // Hide analysis section
        this.elements.analysisSection.style.display = 'none';
    }

    onTestComplete(data) {
        console.log('Test complete. Analysis:', data.analysis);

        this.currentTestId = data.test_id;

        // Display analysis
        this.displayAnalysis(data.analysis);

        // Reload test history
        this.loadTestHistory();
    }

    displayAnalysis(analysis) {
        this.elements.analysisSection.style.display = 'block';

        const metrics = [
            { label: 'Motor Class', value: analysis.motor_class, unit: '', cssClass: 'motor-class' },
            { label: 'Peak Thrust', value: analysis.peak_thrust_n, unit: 'N' },
            { label: 'Average Thrust', value: analysis.avg_thrust_n, unit: 'N' },
            { label: 'Total Impulse', value: analysis.total_impulse_ns, unit: 'N·s' },
            { label: 'Burn Time', value: analysis.burn_time_s, unit: 's' },
            { label: 'Time to Peak', value: analysis.time_to_peak_s, unit: 's' },
            { label: 'Time to 90%', value: analysis.time_to_90pct_s, unit: 's' },
            { label: 'Rise Rate', value: analysis.rise_rate_ns, unit: 'N/s' },
            { label: 'Decay Rate', value: Math.abs(analysis.decay_rate_ns), unit: 'N/s' },
            { label: 'Thrust Stability', value: analysis.thrust_stability_std, unit: 'N (σ)' },
            { label: 'Impulse Efficiency', value: (analysis.impulse_efficiency * 100).toFixed(1), unit: '%' },
            { label: 'Burn Profile', value: analysis.burn_profile, unit: '' },
            { label: 'CATO Detected', value: analysis.cato_detected ? 'YES' : 'NO', unit: '', cssClass: analysis.cato_detected ? 'warning' : '' },
        ];

        let html = '';
        metrics.forEach(metric => {
            html += `
                <div class="metric-card ${metric.cssClass || ''}">
                    <div class="metric-label">${metric.label}</div>
                    <div>
                        <span class="metric-value">${metric.value}</span>
                        <span class="metric-unit">${metric.unit}</span>
                    </div>
                </div>
            `;
        });

        // Add warnings if any
        if (analysis.warnings && analysis.warnings.length > 0) {
            html += `
                <div class="metric-card warning" style="grid-column: 1 / -1;">
                    <div class="metric-label">Warnings</div>
                    <ul style="margin-top: 0.5rem; padding-left: 1.5rem;">
                        ${analysis.warnings.map(w => `<li>${w}</li>`).join('')}
                    </ul>
                </div>
            `;
        }

        this.elements.analysisContent.innerHTML = html;
    }

    loadTestHistory() {
        console.log('Loading test history...');
        this.socket.emit('get_tests');
    }

    displayTestHistory(tests) {
        if (!tests || tests.length === 0) {
            this.elements.historyTbody.innerHTML = `
                <tr>
                    <td colspan="7" style="text-align: center; padding: 20px;">No tests recorded yet</td>
                </tr>
            `;
            return;
        }

        let html = '';
        tests.forEach(test => {
            const date = new Date(test.timestamp).toLocaleString();
            const duration = (test.duration_ms / 1000).toFixed(2);

            html += `
                <tr onclick="app.loadTestDetail(${test.id})">
                    <td>${test.id}</td>
                    <td>${date}</td>
                    <td>${duration} s</td>
                    <td>${test.max_thrust ? test.max_thrust.toFixed(2) : 'N/A'} N</td>
                    <td>${test.total_impulse ? test.total_impulse.toFixed(2) : 'N/A'} N·s</td>
                    <td>${test.motor_class || 'N/A'}</td>
                    <td>
                        <button class="btn btn-small" onclick="event.stopPropagation(); app.downloadTestCSV(${test.id})">CSV</button>
                    </td>
                </tr>
            `;
        });

        this.elements.historyTbody.innerHTML = html;
    }

    loadTestDetail(testId) {
        console.log('Loading test detail:', testId);
        this.socket.emit('get_test_detail', { test_id: testId });
    }

    displayTestDetail(test) {
        console.log('Displaying test detail:', test);

        // Load data into chart
        if (test.data && test.data.readings) {
            const startTime = test.data.readings[0].timestamp;
            const timeArray = test.data.readings.map(r => (r.timestamp - startTime) / 1000.0);
            const forceArray = test.data.readings.map(r => r.force);

            this.chart.setData(timeArray, forceArray);
        }

        // Display analysis
        if (test.analysis) {
            this.displayAnalysis(test.analysis);
        }

        // Set current test ID for CSV download
        this.currentTestId = test.id;
    }

    downloadCSV() {
        if (this.currentTestId) {
            window.location.href = `/api/tests/${this.currentTestId}/csv`;
        }
    }

    downloadTestCSV(testId) {
        window.location.href = `/api/tests/${testId}/csv`;
    }
}

// Initialize app when DOM is ready
let app;
document.addEventListener('DOMContentLoaded', () => {
    console.log('Initializing Rocket Motor Test Stand Dashboard...');
    app = new TestStandApp();
});
