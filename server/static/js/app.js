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

        // Update rate tracking
        this.lastUpdateTime = 0;
        this.updateCount = 0;
        this.updateRateWindow = [];

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

            rawValue: document.getElementById('raw-value'),
            rawMass: document.getElementById('raw-mass'),
            updateRate: document.getElementById('update-rate'),

            btnStartTest: document.getElementById('btn-start-test'),
            btnStopTest: document.getElementById('btn-stop-test'),
            btnTare: document.getElementById('btn-tare'),
            btnCalibrate: document.getElementById('btn-calibrate'),

            analysisSection: document.getElementById('analysis-section'),
            analysisContent: document.getElementById('analysis-content'),
            btnDownloadCSV: document.getElementById('btn-download-csv'),
            btnDownloadPDF: document.getElementById('btn-download-pdf'),
            btnCropData: document.getElementById('btn-crop-data'),

            btnRefreshHistory: document.getElementById('btn-refresh-history'),
            historyTbody: document.getElementById('history-tbody'),

            calibrateModal: document.getElementById('calibrate-modal'),
            knownMassInput: document.getElementById('known-mass-input'),
            btnCalibrateConfirm: document.getElementById('btn-calibrate-confirm'),
            btnCalibrateCancel: document.getElementById('btn-calibrate-cancel'),

            cropModal: document.getElementById('crop-modal'),
            cropStartInput: document.getElementById('crop-start-input'),
            cropEndInput: document.getElementById('crop-end-input'),
            btnCropConfirm: document.getElementById('btn-crop-confirm'),
            btnCropReset: document.getElementById('btn-crop-reset'),
            btnCropCancel: document.getElementById('btn-crop-cancel'),
            cropCurrentStatus: document.getElementById('crop-current-status'),
            cropStatusText: document.getElementById('crop-status-text'),

            testLabelInput: document.getElementById('test-label-input'),
        };

        // Attach event listeners
        this.elements.btnStartTest.addEventListener('click', () => this.startTest());
        this.elements.btnStopTest.addEventListener('click', () => this.stopTest());
        this.elements.btnTare.addEventListener('click', () => this.tare());
        this.elements.btnCalibrate.addEventListener('click', () => this.showCalibrateModal());

        this.elements.btnRefreshHistory.addEventListener('click', () => this.loadTestHistory());
        this.elements.btnDownloadCSV.addEventListener('click', () => this.downloadCSV());
        this.elements.btnDownloadPDF.addEventListener('click', () => this.downloadPDF());
        this.elements.btnCropData.addEventListener('click', () => this.showCropModal());

        this.elements.btnCalibrateConfirm.addEventListener('click', () => this.calibrate());
        this.elements.btnCalibrateCancel.addEventListener('click', () => this.hideCalibrateModal());

        this.elements.btnCropConfirm.addEventListener('click', () => this.cropData());
        this.elements.btnCropReset.addEventListener('click', () => this.resetCrop());
        this.elements.btnCropCancel.addEventListener('click', () => this.hideCropModal());
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
        // Capture start time from first reading when recording starts
        if (this.recording && this.testStartTime === null) {
            this.testStartTime = data.timestamp;
        }

        const time_s = (data.timestamp - (this.testStartTime || data.timestamp)) / 1000.0;
        const force_n = data.force;

        // Update raw values display (always, not just when recording)
        if (data.raw !== undefined) {
            this.elements.rawValue.textContent = data.raw.toLocaleString();
        }

        // Calculate mass from force (reverse: F = m * g, so m = F / g)
        const mass_g = (force_n / 9.81) * 1000;
        this.elements.rawMass.textContent = mass_g.toFixed(2);

        // Calculate update rate
        const now = Date.now();
        if (this.lastUpdateTime > 0) {
            const dt = (now - this.lastUpdateTime) / 1000.0; // seconds
            if (dt > 0) {
                this.updateRateWindow.push(1.0 / dt);
                // Keep last 10 samples
                if (this.updateRateWindow.length > 10) {
                    this.updateRateWindow.shift();
                }
                // Average rate
                const avgRate = this.updateRateWindow.reduce((a, b) => a + b, 0) / this.updateRateWindow.length;
                this.elements.updateRate.textContent = Math.round(avgRate);
            }
        }
        this.lastUpdateTime = now;

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
        const label = this.elements.testLabelInput.value.trim();
        console.log('Starting test with label:', label);
        this.socket.emit('start_test', { label: label });
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
        this.testStartTime = null;  // Will be set from first reading
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
                    <td colspan="8" style="text-align: center; padding: 20px;">No tests recorded yet</td>
                </tr>
            `;
            return;
        }

        let html = '';
        tests.forEach(test => {
            const date = new Date(test.timestamp).toLocaleString();
            const duration = (test.duration_ms / 1000).toFixed(2);
            const label = test.label || '';
            const labelId = `label-${test.id}`;

            html += `
                <tr onclick="app.loadTestDetail(${test.id})">
                    <td>${test.id}</td>
                    <td>
                        <span id="${labelId}" class="editable-label" onclick="event.stopPropagation(); app.editLabel(${test.id})">${label || '<em>click to add</em>'}</span>
                    </td>
                    <td>${date}</td>
                    <td>${duration} s</td>
                    <td>${test.max_thrust ? test.max_thrust.toFixed(2) : 'N/A'} N</td>
                    <td>${test.total_impulse ? test.total_impulse.toFixed(2) : 'N/A'} N·s</td>
                    <td>${test.motor_class || 'N/A'}</td>
                    <td>
                        <button class="btn btn-small" onclick="event.stopPropagation(); app.downloadTestCSV(${test.id})">CSV</button>
                        <button class="btn btn-small" onclick="event.stopPropagation(); app.downloadTestPDF(${test.id})">PDF</button>
                        <button class="btn btn-small btn-danger" onclick="event.stopPropagation(); app.deleteTest(${test.id})">Delete</button>
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

            // Apply crop markers if crop is set
            if (test.crop_start !== null && test.crop_start !== undefined) {
                this.chart.setCropRegion(test.crop_start, test.crop_end);
            } else {
                this.chart.clearCropRegion();
            }
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

    downloadTestPDF(testId) {
        window.location.href = `/api/tests/${testId}/pdf`;
    }

    editLabel(testId) {
        const labelElement = document.getElementById(`label-${testId}`);
        const currentLabel = labelElement.textContent === 'click to add' ? '' : labelElement.textContent;

        const newLabel = prompt('Enter new label:', currentLabel);
        if (newLabel !== null) {
            fetch(`/api/tests/${testId}/label`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ label: newLabel })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    labelElement.textContent = newLabel || 'click to add';
                    labelElement.style.fontStyle = newLabel ? 'normal' : 'italic';
                    console.log('Label updated successfully');
                } else {
                    alert('Failed to update label: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error updating label:', error);
                alert('Failed to update label');
            });
        }
    }

    deleteTest(testId) {
        if (confirm('Are you sure you want to delete this test? This action cannot be undone.')) {
            fetch(`/api/tests/${testId}`, {
                method: 'DELETE'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    console.log('Test deleted successfully');
                    this.loadTestHistory();
                } else {
                    alert('Failed to delete test: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error deleting test:', error);
                alert('Failed to delete test');
            });
        }
    }

    downloadPDF() {
        if (this.currentTestId) {
            window.location.href = `/api/tests/${this.currentTestId}/pdf`;
        }
    }

    showCropModal() {
        // Show current crop status if available
        if (this.chart.cropEnabled) {
            const cropStart = this.chart.cropStart !== null ? this.chart.cropStart.toFixed(2) + 's' : 'none';
            const cropEnd = this.chart.cropEnd !== null ? this.chart.cropEnd.toFixed(2) + 's' : 'end';
            this.elements.cropStatusText.textContent = `${cropStart} to ${cropEnd}`;
            this.elements.cropCurrentStatus.style.display = 'block';

            // Pre-fill inputs with current crop values
            if (this.chart.cropStart !== null) {
                this.elements.cropStartInput.value = this.chart.cropStart;
            }
            if (this.chart.cropEnd !== null) {
                this.elements.cropEndInput.value = this.chart.cropEnd;
            }
        } else {
            this.elements.cropCurrentStatus.style.display = 'none';
        }

        this.elements.cropModal.style.display = 'flex';
    }

    hideCropModal() {
        this.elements.cropModal.style.display = 'none';
        this.elements.cropStartInput.value = '0';
        this.elements.cropEndInput.value = '';
    }

    cropData() {
        if (!this.currentTestId) {
            alert('No test selected');
            return;
        }

        const startTime = parseFloat(this.elements.cropStartInput.value) || 0;
        const endTimeValue = this.elements.cropEndInput.value.trim();
        const endTime = endTimeValue ? parseFloat(endTimeValue) : null;

        fetch(`/api/tests/${this.currentTestId}/crop`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                start_time: startTime,
                end_time: endTime
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('Crop parameters set successfully');
                this.chart.setCropRegion(startTime, endTime);
                this.hideCropModal();
                this.loadTestDetail(this.currentTestId);
                alert(`Crop applied! Data will be filtered from ${startTime}s to ${endTime !== null ? endTime + 's' : 'end'}. Click "Reset Crop" to view full data.`);
            } else {
                alert('Failed to set crop: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error setting crop:', error);
            alert('Failed to set crop');
        });
    }

    resetCrop() {
        if (!this.currentTestId) {
            alert('No test selected');
            return;
        }

        fetch(`/api/tests/${this.currentTestId}/reset_crop`, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('Crop reset successfully');
                this.chart.clearCropRegion();
                this.hideCropModal();
                this.loadTestDetail(this.currentTestId);
                alert('Crop reset - showing full test data');
            } else {
                alert('Failed to reset crop: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error resetting crop:', error);
            alert('Failed to reset crop');
        });
    }
}

// Initialize app when DOM is ready
let app;
document.addEventListener('DOMContentLoaded', () => {
    console.log('Initializing Rocket Motor Test Stand Dashboard...');
    app = new TestStandApp();
});
