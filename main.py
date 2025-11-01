from flask import Flask, jsonify, request, Response
import requests # Used to make HTTP requests from our server to Alpha Vantage

# Initialize the Flask app
app = Flask(__name__)

# Your secret API key is stored securely on the server
ALPHA_VANTAGE_API_KEY = "AF01F23GQ79IIP3X"

# === FRONTEND ROUTE ===
# This serves the main HTML page to the user
@app.route("/")
def serve_frontend():
    """Returns the complete frontend (HTML, CSS, JS) as a single string."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en" class="h-full">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>StockPulse</title>
        <!-- Load Tailwind CSS -->
        <script src="https://cdn.tailwindcss.com"></script>
        <!-- Load Chart.js -->
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0"></script>
        <!-- Use Inter font -->
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            body {
                font-family: 'Inter', sans-serif;
            }
        </style>
    </head>
    <body class="bg-gray-900 text-gray-100 h-full flex items-start justify-center p-4">

        <div class="w-full max-w-4xl bg-gray-800 rounded-2xl shadow-2xl p-6 md:p-8">
            <h1 class="text-3xl font-bold text-center text-white mb-6">Stock Trend Tracker</h1>

            <!-- Input Section -->
            <div class="flex flex-col md:flex-row gap-4 mb-6">
                <div class="flex-1">
                    <label for="stock-ticker" class="block text-sm font-medium text-gray-400 mb-1">Stock Ticker</label>
                    <input type="text" id="stock-ticker" placeholder="e.g., AAPL, MSFT" value="IBM" class="w-full bg-gray-700 border border-gray-600 text-white rounded-lg p-3 focus:ring-2 focus:ring-blue-500 focus:outline-none">
                </div>
                <button id="fetch-button" class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-6 rounded-lg transition duration-200 shadow-lg md:self-end">
                    Get Stock Data
                </button>
            </div>

            <!-- Message/Error Box -->
            <div id="message-box" class="hidden p-4 rounded-lg mb-6 text-center"></div>

            <!-- Data Display Section -->
            <div id="data-container" class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6 hidden">
                <div class="bg-gray-700 p-4 rounded-lg shadow">
                    <div class="text-sm text-gray-400">Symbol</div>
                    <div id="data-symbol" class="text-2xl font-semibold text-white">-</div>
                </div>
                <div class="bg-gray-700 p-4 rounded-lg shadow">
                    <div class="text-sm text-gray-400">Current Price</div>
                    <div id="data-price" class="text-2xl font-semibold text-white">-</div>
                </div>
                <div class="bg-gray-700 p-4 rounded-lg shadow">
                    <div class="text-sm text-gray-400">Change</div>
                    <div id="data-change" class="text-2xl font-semibold text-white">-</div>
                </div>
                <div class="bg-gray-700 p-4 rounded-lg shadow">
                    <div class="text-sm text-gray-400">Change %</div>
                    <div id="data-change-percent" class="text-2xl font-semibold text-white">-</div>
                </div>
            </div>

            <!-- Chart Container -->
            <div class="bg-gray-700 p-4 rounded-lg shadow-inner">
                <canvas id="stock-chart"></canvas>
            </div>
        </div>

        <script>
            // This JavaScript is IDENTICAL to the Java version
            const tickerInput = document.getElementById('stock-ticker');
            const fetchButton = document.getElementById('fetch-button');
            const messageBox = document.getElementById('message-box');
            const dataContainer = document.getElementById('data-container');
            const chartCanvas = document.getElementById('stock-chart');
            
            // Data display elements
            const dataSymbol = document.getElementById('data-symbol');
            const dataPrice = document.getElementById('data-price');
            const dataChange = document.getElementById('data-change');
            const dataChangePercent = document.getElementById('data-change-percent');

            let stockChart; // Variable to hold the chart instance

            // Add event listener
            fetchButton.addEventListener('click', handleFetchData);

            // Main function to orchestrate fetching and display
            async function handleFetchData() {
                const ticker = tickerInput.value.trim().toUpperCase();

                if (!ticker) {
                    showMessage('Please enter a stock ticker.', 'error');
                    return;
                }

                // Show loading state
                fetchButton.disabled = true;
                fetchButton.textContent = 'Loading...';
                showMessage('Fetching data...', 'info');
                dataContainer.classList.add('hidden');

                try {
                    // Fetch data in parallel from OUR OWN backend
                    const [quoteData, timeSeriesData] = await Promise.all([
                        fetchQuote(ticker),
                        fetchTimeSeries(ticker)
                    ]);

                    // 1. Process and display quote data
                    displayQuote(quoteData);

                    // 2. Process and display chart data
                    const { labels, prices } = processTimeSeries(timeSeriesData);
                    
                    // 3. Calculate SMA (Simple Moving Average)
                    const smaData = calculateSMA(prices, 20); // 20-day SMA

                    // 4. Render the chart
                    renderChart(labels, prices, smaData);
                    
                    showMessage('Data loaded successfully!', 'success');
                    dataContainer.classList.remove('hidden');

                } catch (error) {
                    console.error(error);
                    showMessage(error.message, 'error');
                } finally {
                    // Restore button state
                    fetchButton.disabled = false;
                    fetchButton.textContent = 'Get Stock Data';
                }
            }

            // Fetch current quote data
            async function fetchQuote(ticker) {
                // *** MODIFIED: Call our own Python backend API ***
                const url = `/api/quote?ticker=${ticker}`;
                const response = await fetch(url);
                const data = await response.json();

                // Better Error Handling
                if (data['Error Message']) {
                    throw new Error(`API Error: ${data['Error Message']}`);
                }
                if (data['Note']) {
                    // This catches rate limit errors
                    throw new Error(`API Limit: ${data['Note']}`);
                }
                if (data.error) { // This is for our *own* backend error
                    throw new Error(`Backend Error: ${data.error}`);
                }
                if (!data['Global Quote']) {
                    throw new Error('Could not fetch quote. Check API key or ticker.');
                }
                if (Object.keys(data['Global Quote']).length === 0) {
                        throw new Error(`No quote data found for ${ticker}. It might be an invalid symbol.`);
                }
                return data['Global Quote'];
            }

            // Fetch historical time series data
            async function fetchTimeSeries(ticker) {
                // *** MODIFIED: Call our own Python backend API ***
                const url = `/api/timeseries?ticker=${ticker}`;
                const response = await fetch(url);
                const data = await response.json();

                // Better Error Handling
                if (data['Error Message']) {
                    throw new Error(`API Error: ${data['Error Message']}`);
                }
                if (data['Note']) {
                    // This catches rate limit errors
                    throw new Error(`API Limit: ${data['Note']}`);
                }
                if (data.error) { // This is for our *own* backend error
                    throw new Error(`Backend Error: ${data.error}`);
                }
                if (!data['Time Series (Daily)']) {
                    throw new Error('Could not fetch historical data. Check API key or ticker.');
                }
                return data['Time Series (Daily)'];
            }

            // Display the quote data in the summary boxes
            function displayQuote(quote) {
                const price = parseFloat(quote['05. price']);
                const change = parseFloat(quote['09. change']);
                const changePercent = parseFloat(quote['10. change percent']);
                
                dataSymbol.textContent = quote['01. symbol'];
                dataPrice.textContent = `$${price.toFixed(2)}`;
                dataChange.textContent = `${change.toFixed(2)}`;
                dataChangePercent.textContent = `${changePercent.toFixed(2)}%`;

                // Color-code the change
                [dataChange, dataChangePercent].forEach(el => {
                    if (change > 0) {
                        el.classList.remove('text-red-400');
                        el.classList.add('text-green-400');
                    } else if (change < 0) {
                        el.classList.remove('text-green-400');
                        el.classList.add('text-red-400');
                    } else {
                        el.classList.remove('text-green-400', 'text-red-400');
                        el.classList.add('text-white');
                    }
                });
            }

            // Process raw time series data for the chart
            function processTimeSeries(timeSeries) {
                // Get the last 100 entries, sort them from oldest to newest
                // Note: Object.entries works the same on JS objects as dict.items() in Python
                const entries = Object.entries(timeSeries).slice(0, 100).reverse();
                
                const labels = entries.map(entry => entry[0]); // Dates
                const prices = entries.map(entry => parseFloat(entry[1]['4. close'])); // Closing prices

                return { labels, prices };
            }

            // Calculate Simple Moving Average
            function calculateSMA(data, period) {
                const sma = [];
                for (let i = 0; i < data.length; i++) {
                    if (i < period - 1) {
                        // Not enough data for SMA, push null
                        sma.push(null); 
                    } else {
                        // Calculate sum of the past 'period' data points
                        let sum = 0;
                        for (let j = 0; j < period; j++) {
                            sum += data[i - j];
                        }
                        sma.push(sum / period);
                    }
                }
                return sma;
            }

            // Render the chart using Chart.js
            function renderChart(labels, prices, smaData) {
                if (stockChart) {
                    stockChart.destroy(); // Clear previous chart
                }

                const ctx = chartCanvas.getContext('2d');
                stockChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [
                            {
                                label: 'Closing Price',
                                data: prices,
                                borderColor: 'rgb(59, 130, 246)', // Blue
                                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                                borderWidth: 2,
                                pointRadius: 0,
                                fill: true,
                                tension: 0.1
                            },
                            {
                                label: '20-Day SMA (Trend)',
                                data: smaData,
                                borderColor: 'rgb(234, 179, 8)', // Yellow
                                borderWidth: 2,
                                pointRadius: 0,
                                borderDash: [5, 5], // Dashed line
                                fill: false,
                                tension: 0.1
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: true,
                        plugins: {
                            legend: {
                                labels: {
                                    color: '#d1d5db' // gray-300
                                }
                            },
                            tooltip: {
                                mode: 'index',
                                intersect: false
                            }
                        },
                        scales: {
                            x: {
                                type: 'time',
                                time: {
                                    unit: 'day',
                                    tooltipFormat: 'MMM dd, yyyy'
                                },
                                ticks: {
                                    color: '#9ca3af' // gray-400
                                },
                                grid: {
                                    color: 'rgba(255, 255, 255, 0.1)'
                                }
                            },
                            y: {
                                ticks: {
                                    color: '#9ca3af', // gray-400
                                    callback: function(value) {
                                        return '$' + value;
                                    }
                                },
                                grid: {
                                    color: 'rgba(255, 255, 255, 0.1)'
                                }
                            }
                        }
                    }
                });
            }

            // Show a message to the user
            function showMessage(message, type = 'info') {
                messageBox.textContent = message;
                messageBox.classList.remove('hidden', 'bg-red-900', 'bg-green-900', 'bg-blue-900', 'text-red-100', 'text-green-100', 'text-blue-100');

                if (type === 'error') {
                    messageBox.classList.add('bg-red-900', 'text-red-100');
                } else if (type === 'success') {
                    messageBox.classList.add('bg-green-900', 'text-green-100');
                } else {
                    messageBox.classList.add('bg-blue-900', 'text-blue-100');
                }
            }
        </script>
    </body>
    </html>
    """
    return Response(html_content, mimetype='text/html')

# === BACKEND API ROUTES ===

# 1. API endpoint to get the current quote
@app.route("/api/quote")
def get_quote():
    ticker = request.args.get('ticker')
    if not ticker:
        return jsonify({"error": "Ticker symbol is required"}), 400

    api_url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={ALPHA_VANTAGE_API_KEY}"
    
    try:
        response = requests.get(api_url)
        response.raise_for_status() # Raise an exception for bad status codes
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching quote: {e}")
        return jsonify({"error": "Failed to fetch data from external API"}), 500

# 2. API endpoint to get the historical time series
@app.route("/api/timeseries")
def get_timeseries():
    ticker = request.args.get('ticker')
    if not ticker:
        return jsonify({"error": "Ticker symbol is required"}), 400

    api_url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={ticker}&outputsize=compact&apikey={ALPHA_VANTAGE_API_KEY}"
    
    try:
        response = requests.get(api_url)
        response.raise_for_status() # Raise an exception for bad status codes
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching time series: {e}")
        return jsonify({"error": "Failed to fetch data from external API"}), 500

# This block allows the script to be run directly
if __name__ == "__main__":
    print("Stock App server running on http://localhost:5000")
    app.run(debug=True, port=5000) # Runs the server on port 5000
