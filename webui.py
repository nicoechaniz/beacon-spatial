#!/usr/bin/env python3
"""Flask web UI for Harmonic Beacon Spatializer.

Serves a dark-themed control surface (default http://localhost:5050)
Sends OSC to sclang (beacon.scd) on port 57120.

Usage:
    ./start-beacon.sh
    # or manually:
    #   source venv/bin/activate
    #   python3 webui.py
"""

from flask import Flask, render_template_string, request, jsonify
from pythonosc.udp_client import SimpleUDPClient
import os, json, glob

app = Flask(__name__)
osc = SimpleUDPClient("127.0.0.1", 57120)

CONFIG_DIR = os.path.expanduser("~/Projects/beacon-spatial/configs")
os.makedirs(CONFIG_DIR, exist_ok=True)

BANDS = [
    {"freq": 40,   "color": "#c0392b", "default_gain": 1.2, "default_az": 180, "default_dist": 2.0, "default_q": 1.0,   "default_solo": 0},
    {"freq": 80,   "color": "#e67e22", "default_gain": 1.0, "default_az": 135, "default_dist": 2.5, "default_q": 0.5,   "default_solo": 0},
    {"freq": 120,  "color": "#f1c40f", "default_gain": 1.0, "default_az": -90, "default_dist": 3.0, "default_q": 0.333, "default_solo": 0},
    {"freq": 160,  "color": "#2ecc71", "default_gain": 1.0, "default_az": -45, "default_dist": 2.5, "default_q": 0.25,  "default_solo": 0},
    {"freq": 200,  "color": "#1abc9c", "default_gain": 1.0, "default_az": 45,  "default_dist": 2.0, "default_q": 0.2,   "default_solo": 0},
    {"freq": 240,  "color": "#3498db", "default_gain": 1.3, "default_az": 0,   "default_dist": 1.5, "default_q": 0.167, "default_solo": 0},
    {"freq": 480,  "color": "#2980b9", "default_gain": 1.0, "default_az": 0,   "default_dist": 2.0, "default_q": 0.5,   "default_solo": 0},
    {"freq": 720,  "color": "#8e44ad", "default_gain": 1.0, "default_az": 0,   "default_dist": 2.0, "default_q": 0.333, "default_solo": 0},
    {"freq": 960,  "color": "#9b59b6", "default_gain": 1.0, "default_az": 0,   "default_dist": 2.0, "default_q": 0.25,  "default_solo": 0},
    {"freq": 1200, "color": "#e84393", "default_gain": 1.0, "default_az": 0,   "default_dist": 2.0, "default_q": 0.2,   "default_solo": 0},
    {"freq": 1440, "color": "#fd79a8", "default_gain": 1.0, "default_az": 0,   "default_dist": 2.0, "default_q": 0.167, "default_solo": 0},
    {"freq": 1680, "color": "#a29bfe", "default_gain": 1.0, "default_az": 0,   "default_dist": 2.0, "default_q": 0.143, "default_solo": 0},
    {"freq": "1800+", "color": "#dfe6e9", "default_gain": 1.0, "default_az": 0,   "default_dist": 2.0, "default_solo": 0},
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
            margin-bottom: 12px;
            font-size: 0.85rem;
        }
        .spectrum {
            display: flex;
            align-items: flex-end;
            justify-content: center;
            gap: 4px;
            height: 80px;
            max-width: 1200px;
            margin: 0 auto 20px;
            padding: 10px;
            background: #0d0d14;
            border-radius: 8px;
            border: 1px solid #1a1a2e;
        }
        .spectrum-bar {
            flex: 1;
            min-width: 4px;
            border-radius: 2px 2px 0 0;
            transition: height 0.1s;
            opacity: 0.85;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(13, 1fr);
            gap: 8px;
            max-width: 1200px;
            margin: 0 auto 20px;
        }
        .band {
            background: #12121a;
            border-radius: 10px;
            padding: 10px 4px;
            text-align: center;
            border: 1px solid #1a1a2e;
            transition: opacity 0.2s;
        }
        .band-label {
            font-size: 0.65rem;
            font-weight: 600;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .fader-container {
            height: 120px;
            display: flex;
            justify-content: center;
            align-items: center;
            margin-bottom: 8px;
        }
        input[type=range][orient=vertical] {
            writing-mode: bt-lr;
            -webkit-appearance: slider-vertical;
            width: 24px;
            height: 110px;
        }
        input[type=range] {
            -webkit-appearance: none;
            background: transparent;
            cursor: pointer;
        }
        input[type=range]::-webkit-slider-thumb {
            -webkit-appearance: none;
            height: 14px;
            width: 14px;
            border-radius: 50%;
            background: currentColor;
            margin-top: -5px;
            box-shadow: 0 0 6px currentColor;
        }
        input[type=range]::-webkit-slider-runnable-track {
            height: 4px;
            background: #2a2a3e;
            border-radius: 2px;
        }
        .param {
            margin-bottom: 6px;
        }
        .param label {
            display: block;
            font-size: 0.55rem;
            color: #888;
            margin-bottom: 2px;
            text-transform: uppercase;
        }
        .param input[type=range] {
            width: 100%;
        }
        .value {
            font-size: 0.65rem;
            color: #aaa;
            margin-top: 1px;
        }
        .solo-btn {
            display: inline-block;
            padding: 3px 8px;
            font-size: 0.55rem;
            font-weight: 700;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            border: 1px solid #444;
            border-radius: 3px;
            background: transparent;
            color: #666;
            cursor: pointer;
            margin-top: 2px;
            transition: all 0.15s;
        }
        .solo-btn.active {
            background: #fff;
            color: #000;
            border-color: #fff;
            box-shadow: 0 0 8px rgba(255,255,255,0.4);
        }
        .band.muted {
            opacity: 0.3;
        }
        .mix-section, .config-section {
            max-width: 1200px;
            margin: 0 auto 16px;
            background: #12121a;
            border-radius: 12px;
            padding: 16px;
            border: 1px solid #1a1a2e;
        }
        .mix-section h2, .config-section h2 {
            font-size: 0.85rem;
            font-weight: 400;
            margin-bottom: 12px;
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
        .config-grid {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 12px;
            align-items: end;
        }
        .config-col {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }
        .config-col label {
            font-size: 0.6rem;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .config-col input[type=text], .config-col select {
            background: #0d0d14;
            border: 1px solid #2a2a3e;
            color: #e0e0e0;
            padding: 8px;
            border-radius: 6px;
            font-size: 0.8rem;
        }
        .config-col button {
            padding: 8px;
            border-radius: 6px;
            border: 1px solid;
            background: transparent;
            cursor: pointer;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .btn-reset { color: #e67e22; border-color: #e67e22; }
        .btn-reset:hover { background: #e67e22; color: #000; }
        .btn-save { color: #2ecc71; border-color: #2ecc71; }
        .btn-save:hover { background: #2ecc71; color: #000; }
        .btn-load { color: #3498db; border-color: #3498db; }
        .btn-load:hover { background: #3498db; color: #000; }
        .section-label {
            text-align: center;
            color: #555;
            font-size: 0.7rem;
            margin: 12px 0 6px;
            letter-spacing: 2px;
            text-transform: uppercase;
        }
        @media (max-width: 1100px) {
            .grid { grid-template-columns: repeat(7, 1fr); }
        }
        @media (max-width: 768px) {
            .grid { grid-template-columns: repeat(4, 1fr); }
            .mix-grid { grid-template-columns: repeat(2, 1fr); }
            .config-grid { grid-template-columns: 1fr; }
        }
        @media (max-width: 480px) {
            .grid { grid-template-columns: repeat(3, 1fr); }
        }
    </style>
</head>
<body>
    <h1>Harmonic Beacon</h1>
    <p class="subtitle">13-band binaural spatializer — 40Hz series + high harmonics</p>
    
    <div class="spectrum" id="spectrum">
        {% for band in bands %}
        <div class="spectrum-bar" id="spec{{ loop.index }}" style="background: {{ band.color }}; height: {{ band.default_gain / 3.0 * 100 }}%"></div>
        {% endfor %}
    </div>
    
    <div class="section-label">Low bands (40Hz BW)</div>
    <div class="grid">
        {% for band in bands %}
        <div class="band" id="band{{ loop.index }}" style="color: {{ band.color }}">
            <div class="band-label" style="color: {{ band.color }}">{{ band.freq }}Hz</div>
            <div class="fader-container">
                <input type="range" orient="vertical" min="0" max="3" step="0.05"
                       value="{{ band.default_gain }}" id="gain{{ loop.index }}"
                       oninput="send('gain', {{ loop.index }}, this.value); show(this, 'g{{ loop.index }}'); updateSpec({{ loop.index }}, this.value)">
            </div>
            <div class="value" id="g{{ loop.index }}">{{ band.default_gain }}</div>
            <div class="param">
                <label>Az</label>
                <input type="range" min="-180" max="180" step="1"
                       value="{{ band.default_az }}" id="az{{ loop.index }}"
                       oninput="send('az', {{ loop.index }}, this.value); show(this, 'a{{ loop.index }}')">
                <div class="value" id="a{{ loop.index }}">{{ band.default_az }}&deg;</div>
            </div>
            <div class="param">
                <label>Dist</label>
                <input type="range" min="0" max="10" step="0.1"
                       value="{{ band.default_dist }}" id="dist{{ loop.index }}"
                       oninput="send('dist', {{ loop.index }}, this.value); show(this, 'd{{ loop.index }}')">
                <div class="value" id="d{{ loop.index }}">{{ band.default_dist }}</div>
            </div>
            {% if band.default_q is defined %}
            <div class="param">
                <label>Q</label>
                <input type="range" min="0.01" max="2.0" step="0.001"
                       value="{{ band.default_q }}" id="q{{ loop.index }}"
                       oninput="send('q', {{ loop.index }}, this.value); show(this, 'q{{ loop.index }}')">
                <div class="value" id="q{{ loop.index }}">{{ band.default_q }}</div>
            </div>
            {% endif %}
            <button id="s{{ loop.index }}" class="solo-btn"
                    onclick="toggleSolo({{ loop.index }}, this)">Solo</button>
        </div>
        {% endfor %}
    </div>
    
    <div class="mix-section">
        <h2>Mix & Master</h2>
        <div class="mix-grid">
            <div class="mix-param">
                <label style="display:block; font-size:0.7rem; color:#1abc9c; margin-bottom:8px;">MIX (wet)</label>
                <input type="range" min="0" max="1" step="0.01" value="0.85" id="mix"
                       oninput="sendGlobal('mix', this.value); show(this, 'vmix')">
                <div class="value" id="vmix">0.85</div>
            </div>
            <div class="mix-param">
                <label style="display:block; font-size:0.7rem; color:#34495e; margin-bottom:8px;">MASTER</label>
                <input type="range" min="0" max="2" step="0.01" value="0.9" id="master"
                       oninput="sendGlobal('master', this.value); show(this, 'vmaster')">
                <div class="value" id="vmaster">0.90</div>
            </div>
            <div class="mix-param">
                <label style="display:block; font-size:0.7rem; color:#e74c3c; margin-bottom:8px;">REC</label>
                <button id="rec-btn" class="solo-btn" style="border-color:#e74c3c; color:#e74c3c; width:100%; padding:6px;"
                        onclick="toggleRecord(this)">RECORD</button>
                <div class="value" id="vrec">ready</div>
            </div>
            <div class="mix-param">
                <label style="display:block; font-size:0.7rem; color:#e67e22; margin-bottom:8px;">RESET</label>
                <button class="solo-btn" style="border-color:#e67e22; color:#e67e22; width:100%; padding:6px;"
                        onclick="resetAll()">RESET ALL</button>
                <div class="value" id="vreset">defaults</div>
            </div>
        </div>
    </div>
    
    <div class="config-section">
        <h2>Presets</h2>
        <div class="config-grid">
            <div class="config-col">
                <label>Save current as</label>
                <input type="text" id="save-name" placeholder="my-preset">
                <button class="btn-save" onclick="saveConfig()">Save</button>
            </div>
            <div class="config-col">
                <label>Load preset</label>
                <select id="load-select"><option value="">-- select --</option></select>
                <button class="btn-load" onclick="loadConfig()">Load</button>
            </div>
            <div class="config-col">
                <label>Status</label>
                <div class="value" id="config-status" style="padding-top:8px;">Ready</div>
            </div>
        </div>
    </div>
    
    <script>
        const defaults = {
            gains: [1.2, 1.0, 1.0, 1.0, 1.0, 1.3, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            azs:   [180, 135, -90, -45, 45, 0, 0, 0, 0, 0, 0, 0, 0],
            dists: [2.0, 2.5, 3.0, 2.5, 2.0, 1.5, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0],
            qs:    [1.0, 0.5, 0.333, 0.25, 0.2, 0.167, 0.5, 0.333, 0.25, 0.2, 0.167, 0.143],
            solos: [0,0,0,0,0,0,0,0,0,0,0,0,0],
            mix: 0.85, master: 0.9
        };

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
            const unit = id.startsWith('a') ? '&deg;' : '';
            document.getElementById(id).textContent = el.value + unit;
        }
        function updateSpec(band, value) {
            const bar = document.getElementById('spec' + band);
            if (bar) bar.style.height = (value / 3.0 * 100) + '%';
        }
        let recording = false;
        function toggleRecord(btn) {
            recording = !recording;
            if (recording) {
                const label = 'session_' + new Date().toISOString().slice(0,19).replace(/[:T]/g,'-');
                sendGlobal('record/start', label);
                btn.textContent = 'STOP';
                btn.classList.add('active');
                btn.style.background = '#e74c3c';
                btn.style.color = '#fff';
                btn.style.borderColor = '#e74c3c';
                document.getElementById('vrec').textContent = 'recording...';
            } else {
                sendGlobal('record/stop', 0);
                btn.textContent = 'RECORD';
                btn.classList.remove('active');
                btn.style.background = 'transparent';
                btn.style.color = '#e74c3c';
                btn.style.borderColor = '#e74c3c';
                document.getElementById('vrec').textContent = 'saved';
            }
        }
        const soloState = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
        function toggleSolo(band, btn) {
            soloState[band - 1] = soloState[band - 1] ? 0 : 1;
            const isActive = soloState[band - 1];
            btn.classList.toggle('active', isActive);
            send('solo', band, isActive ? 1 : 0);
            const anySolo = soloState.some(s => s === 1);
            for (let i = 1; i <= 13; i++) {
                const card = document.getElementById('band' + i);
                if (anySolo && !soloState[i - 1]) {
                    card.classList.add('muted');
                } else {
                    card.classList.remove('muted');
                }
            }
        }

        function resetAll() {
            // Send reset to scsynth
            sendGlobal('reset', 1);
            // Reset UI
            for (let i = 1; i <= 13; i++) {
                const g = document.getElementById('gain' + i);
                const a = document.getElementById('az' + i);
                const d = document.getElementById('dist' + i);
                const q = document.getElementById('q' + i);
                const s = document.getElementById('s' + i);
                if (g) { g.value = defaults.gains[i-1]; show(g, 'g'+i); updateSpec(i, g.value); }
                if (a) { a.value = defaults.azs[i-1]; show(a, 'a'+i); }
                if (d) { d.value = defaults.dists[i-1]; show(d, 'd'+i); }
                if (q) { q.value = defaults.qs[i-1]; show(q, 'q'+i); }
                if (s && soloState[i-1]) { toggleSolo(i, s); }
            }
            const mix = document.getElementById('mix');
            const master = document.getElementById('master');
            mix.value = defaults.mix; show(mix, 'vmix');
            master.value = defaults.master; show(master, 'vmaster');
            document.getElementById('vreset').textContent = 'reset done';
            setTimeout(() => document.getElementById('vreset').textContent = 'defaults', 1500);
        }

        function gatherState() {
            const state = { bands: [], mix: parseFloat(document.getElementById('mix').value), master: parseFloat(document.getElementById('master').value) };
            for (let i = 1; i <= 13; i++) {
                const b = { gain: parseFloat(document.getElementById('gain'+i).value), az: parseFloat(document.getElementById('az'+i).value), dist: parseFloat(document.getElementById('dist'+i).value), solo: soloState[i-1] };
                const q = document.getElementById('q'+i);
                if (q) b.q = parseFloat(q.value);
                state.bands.push(b);
            }
            return state;
        }

        function applyState(state) {
            for (let i = 1; i <= 13; i++) {
                const b = state.bands[i-1];
                const g = document.getElementById('gain'+i);
                const a = document.getElementById('az'+i);
                const d = document.getElementById('dist'+i);
                const q = document.getElementById('q'+i);
                const s = document.getElementById('s'+i);
                if (g) { g.value = b.gain; send('gain', i, b.gain); show(g, 'g'+i); updateSpec(i, b.gain); }
                if (a) { a.value = b.az; send('az', i, b.az); show(a, 'a'+i); }
                if (d) { d.value = b.dist; send('dist', i, b.dist); show(d, 'd'+i); }
                if (q && b.q !== undefined) { q.value = b.q; send('q', i, b.q); show(q, 'q'+i); }
                if (s && b.solo !== soloState[i-1]) { toggleSolo(i, s); }
            }
            const mix = document.getElementById('mix');
            const master = document.getElementById('master');
            mix.value = state.mix; sendGlobal('mix', state.mix); show(mix, 'vmix');
            master.value = state.master; sendGlobal('master', state.master); show(master, 'vmaster');
        }

        function saveConfig() {
            const name = document.getElementById('save-name').value.trim();
            if (!name) { setStatus('Enter a name'); return; }
            fetch('/save_config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name: name, state: gatherState()})
            }).then(r => r.json()).then(data => {
                setStatus(data.ok ? 'Saved: ' + name : 'Error');
                if (data.ok) loadConfigList();
            });
        }

        function loadConfig() {
            const name = document.getElementById('load-select').value;
            if (!name) { setStatus('Select a preset'); return; }
            fetch('/load_config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name: name})
            }).then(r => r.json()).then(data => {
                if (data.ok && data.state) {
                    applyState(data.state);
                    setStatus('Loaded: ' + name);
                } else {
                    setStatus('Error loading');
                }
            });
        }

        function setStatus(msg) {
            document.getElementById('config-status').textContent = msg;
        }

        function loadConfigList() {
            fetch('/list_configs').then(r => r.json()).then(data => {
                const sel = document.getElementById('load-select');
                sel.innerHTML = '<option value="">-- select --</option>';
                (data.configs || []).forEach(c => {
                    const opt = document.createElement('option');
                    opt.value = c;
                    opt.textContent = c;
                    sel.appendChild(opt);
                });
            });
        }

        loadConfigList();
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

@app.route("/save_config", methods=["POST"])
def save_config():
    data = request.get_json()
    name = data.get("name", "").strip()
    state = data.get("state", {})
    if not name:
        return jsonify({"ok": False, "error": "No name"})
    path = os.path.join(CONFIG_DIR, name + ".json")
    with open(path, "w") as f:
        json.dump(state, f, indent=2)
    return jsonify({"ok": True})

@app.route("/list_configs")
def list_configs():
    files = sorted(glob.glob(os.path.join(CONFIG_DIR, "*.json")))
    configs = [os.path.splitext(os.path.basename(f))[0] for f in files]
    return jsonify({"ok": True, "configs": configs})

@app.route("/load_config", methods=["POST"])
def load_config():
    data = request.get_json()
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"ok": False, "error": "No name"})
    path = os.path.join(CONFIG_DIR, name + ".json")
    if not os.path.exists(path):
        return jsonify({"ok": False, "error": "Not found"})
    with open(path) as f:
        state = json.load(f)
    return jsonify({"ok": True, "state": state})

if __name__ == "__main__":
    print("=" * 50)
    print("Harmonic Beacon Web UI")
    print("=" * 50)
    print("Open your browser at: http://localhost:5050")
    print("Make sure start-beacon.sh (scsynth + sclang/beacon.scd) is running!")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5050, debug=False)
