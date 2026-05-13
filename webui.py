#!/usr/bin/env python3
"""Flask web UI for Harmonic Beacon Spatializer.

Serves a dark-themed control surface (default http://localhost:5050)
Sends OSC directly to Pd on port 9001.

Usage:
    source venv/bin/activate
    python3 webui.py
"""

from flask import Flask, render_template_string, request, jsonify
from pythonosc.udp_client import SimpleUDPClient
import os

app = Flask(__name__)
osc = SimpleUDPClient("127.0.0.1", 9001)

BANDS = [
    {"freq": 40,  "color": "#c0392b", "default_gain": 1.2, "default_az": 180, "default_dist": 2.0},
    {"freq": 80,  "color": "#e67e22", "default_gain": 1.0, "default_az": 135, "default_dist": 2.5},
    {"freq": 120, "color": "#f1c40f", "default_gain": 1.0, "default_az": -90, "default_dist": 3.0},
    {"freq": 160, "color": "#2ecc71", "default_gain": 1.0, "default_az": -45, "default_dist": 2.5},
    {"freq": 200, "color": "#3498db", "default_gain": 1.0, "default_az": 45,  "default_dist": 2.0},
    {"freq": 240, "color": "#9b59b6", "default_gain": 1.3, "default_az": 0,   "default_dist": 1.5},
]

HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Harmonic Beacon Spatializer</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background: #0a0a0f;
            color: #e0e0e0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            padding: 20px;
            min-height: 100vh;
        }
        h1 {
            text-align: center;
            margin-bottom: 8px;
            font-weight: 300;
            letter-spacing: 2px;
            font-size: 1.5rem;
        }
        .subtitle {
            text-align: center;
            color: #666;
            margin-bottom: 24px;
            font-size: 0.85rem;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 12px;
            max-width: 1200px;
            margin: 0 auto 24px;
        }
        .band {
            background: #12121a;
            border-radius: 12px;
            padding: 16px 8px;
            text-align: center;
            border: 1px solid #1a1a2e;
        }
        .band-label {
            font-size: 0.75rem;
            font-weight: 600;
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .fader-container {
            height: 180px;
            display: flex;
            justify-content: center;
            align-items: center;
            margin-bottom: 12px;
        }
        input[type=range][orient=vertical] {
            writing-mode: bt-lr;
            -webkit-appearance: slider-vertical;
            width: 30px;
            height: 160px;
        }
        input[type=range] {
            -webkit-appearance: none;
            background: transparent;
            cursor: pointer;
        }
        input[type=range]::-webkit-slider-thumb {
            -webkit-appearance: none;
            height: 16px;
            width: 16px;
            border-radius: 50%;
            background: currentColor;
            margin-top: -6px;
            box-shadow: 0 0 8px currentColor;
        }
        input[type=range]::-webkit-slider-runnable-track {
            height: 4px;
            background: #2a2a3e;
            border-radius: 2px;
        }
        .param {
            margin-bottom: 10px;
        }
        .param label {
            display: block;
            font-size: 0.65rem;
            color: #888;
            margin-bottom: 4px;
            text-transform: uppercase;
        }
        .param input[type=range] {
            width: 100%;
        }
        .value {
            font-size: 0.75rem;
            color: #aaa;
            margin-top: 2px;
        }
        .mix-section {
            max-width: 1200px;
            margin: 0 auto;
            background: #12121a;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #1a1a2e;
        }
        .mix-section h2 {
            font-size: 0.9rem;
            font-weight: 400;
            margin-bottom: 16px;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        .mix-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
        }
        .mix-param {
            text-align: center;
        }
        .mix-param input[type=range] {
            width: 100%;
        }
        @media (max-width: 768px) {
            .grid { grid-template-columns: repeat(3, 1fr); }
            .mix-grid { grid-template-columns: repeat(2, 1fr); }
        }
    </style>
</head>
<body>
    <h1>Harmonic Beacon</h1>
    <p class="subtitle">6-band binaural spatializer — 40Hz series</p>
    
    <div class="grid">
        {% for band in bands %}
        <div class="band" style="color: {{ band.color }}">
            <div class="band-label" style="color: {{ band.color }}">{{ band.freq }}Hz</div>
            
            <div class="fader-container">
                <input type="range" orient="vertical" min="0" max="3" step="0.05"
                       value="{{ band.default_gain }}"
                       oninput="send('gain', {{ loop.index }}, this.value); show(this, 'g{{ loop.index }}')">
            </div>
            <div class="value" id="g{{ loop.index }}">{{ band.default_gain }}</div>
            
            <div class="param">
                <label>Azimuth</label>
                <input type="range" min="-180" max="180" step="1"
                       value="{{ band.default_az }}"
                       oninput="send('az', {{ loop.index }}, this.value); show(this, 'a{{ loop.index }}')">
                <div class="value" id="a{{ loop.index }}">{{ band.default_az }}°</div>
            </div>
            
            <div class="param">
                <label>Distance</label>
                <input type="range" min="0" max="10" step="0.1"
                       value="{{ band.default_dist }}"
                       oninput="send('dist', {{ loop.index }}, this.value); show(this, 'd{{ loop.index }}')">
                <div class="value" id="d{{ loop.index }}">{{ band.default_dist }}</div>
            </div>
        </div>
        {% endfor %}
    </div>
    
    <div class="mix-section">
        <h2>Mix & Master</h2>
        <div class="mix-grid">
            <div class="mix-param">
                <label style="display:block; font-size:0.7rem; color:#1abc9c; margin-bottom:8px;">WET</label>
                <input type="range" min="0" max="1" step="0.01" value="0.85"
                       oninput="sendGlobal('wet', this.value); show(this, 'vwet')">
                <div class="value" id="vwet">0.85</div>
            </div>
            <div class="mix-param">
                <label style="display:block; font-size:0.7rem; color:#e74c3c; margin-bottom:8px;">DRY</label>
                <input type="range" min="0" max="1" step="0.01" value="0.3"
                       oninput="sendGlobal('dry', this.value); show(this, 'vdry')">
                <div class="value" id="vdry">0.30</div>
            </div>
            <div class="mix-param">
                <label style="display:block; font-size:0.7rem; color:#34495e; margin-bottom:8px;">MASTER</label>
                <input type="range" min="0" max="2" step="0.01" value="0.9"
                       oninput="sendGlobal('master', this.value); show(this, 'vmaster')">
                <div class="value" id="vmaster">0.90</div>
            </div>
            <div class="mix-param">
                <label style="display:block; font-size:0.7rem; color:#9b59b6; margin-bottom:8px;">BUTTERFLY CENTER</label>
                <input type="range" min="-180" max="180" step="1" value="0"
                       oninput="sendGlobal('lfo/offset', this.value); show(this, 'vlfo')">
                <div class="value" id="vlfo">0°</div>
            </div>
        </div>
    </div>
    
    <script>
        function send(param, band, value) {
            fetch('/control', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({address: '/beacon/' + param + '/' + band, value: parseFloat(value)})
            });
        }
        function sendGlobal(param, value) {
            fetch('/control', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({address: '/beacon/' + param, value: parseFloat(value)})
            });
        }
        function show(el, id) {
            const unit = id.startsWith('a') || id === 'vlfo' ? '°' : '';
            document.getElementById(id).textContent = el.value + unit;
        }
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML, bands=BANDS)

@app.route("/control", methods=["POST"])
def control():
    data = request.get_json()
    addr = data.get("address", "")
    val = data.get("value", 0)
    osc.send_message(addr, float(val))
    return jsonify({"ok": True})

if __name__ == "__main__":
    print("=" * 50)
    print("Harmonic Beacon Web UI")
    print("=" * 50)
    print("Open your browser at: http://localhost:5050")
    print("Make sure Pd is running with beacon-spatial.pd!")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5050, debug=False)
