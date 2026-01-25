/**
 * Chart.js configuration for real-time thrust plotting
 */

class ThrustChart {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.dataPoints = [];
        this.maxDataPoints = 3000; // Keep last 3000 points (~37.5 seconds at 80Hz)

        this.chart = new Chart(this.ctx, {
            type: 'line',
            data: {
                datasets: [{
                    label: 'Thrust (N)',
                    data: [],
                    borderColor: 'rgb(37, 99, 235)',
                    backgroundColor: 'rgba(37, 99, 235, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1,
                    pointRadius: 0, // No points for performance
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false, // Critical for performance with real-time data
                interaction: {
                    mode: 'nearest',
                    axis: 'x',
                    intersect: false
                },
                plugins: {
                    legend: {
                        display: true,
                        labels: {
                            color: '#cbd5e1',
                            font: {
                                size: 12
                            }
                        }
                    },
                    tooltip: {
                        enabled: true,
                        mode: 'index',
                        intersect: false
                    }
                },
                scales: {
                    x: {
                        type: 'linear',
                        title: {
                            display: true,
                            text: 'Time (s)',
                            color: '#cbd5e1'
                        },
                        ticks: {
                            color: '#cbd5e1'
                        },
                        grid: {
                            color: '#475569'
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Thrust (N)',
                            color: '#cbd5e1'
                        },
                        ticks: {
                            color: '#cbd5e1'
                        },
                        grid: {
                            color: '#475569'
                        },
                        beginAtZero: true
                    }
                }
            }
        });
    }

    addPoint(time_s, force_n) {
        // Add data point
        this.dataPoints.push({ x: time_s, y: force_n });

        // Limit buffer size
        if (this.dataPoints.length > this.maxDataPoints) {
            this.dataPoints.shift();
        }

        // Update chart data
        this.chart.data.datasets[0].data = this.dataPoints;

        // Update chart (use 'none' mode for best performance)
        this.chart.update('none');
    }

    clear() {
        this.dataPoints = [];
        this.chart.data.datasets[0].data = [];
        this.chart.update();
    }

    setData(timeArray, forceArray) {
        // Load existing test data
        this.dataPoints = timeArray.map((t, i) => ({ x: t, y: forceArray[i] }));
        this.chart.data.datasets[0].data = this.dataPoints;
        this.chart.update();
    }

    updateXAxisRange(minTime, maxTime) {
        // Auto-scale X axis for rolling window
        this.chart.options.scales.x.min = minTime;
        this.chart.options.scales.x.max = maxTime;
    }

    enableAutoScroll(enabled) {
        if (enabled) {
            // Auto-scroll mode: show last 30 seconds
            this.chart.options.scales.x.min = undefined;
            this.chart.options.scales.x.max = undefined;
        }
    }
}
