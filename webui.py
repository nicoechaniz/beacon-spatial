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
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
import os, json, glob, threading, subprocess

app = Flask(__name__)
osc = SimpleUDPClient("127.0.0.1", 57120)
# Second OSC target: PD replica sclang on port 9001 (when running)
osc_pd = SimpleUDPClient("127.0.0.1", 9001)

# OSC-in: recibe el VU de entrada que reenvía sclang (/inlevel) → lo expone en /level para el browser
_LATEST = {"level": 0.0}
def _on_inlevel(addr, *args):
    try:
        _LATEST["level"] = float(args[-1])
    except (TypeError, ValueError):
        pass
def _start_osc_in():
    disp = Dispatcher()
    disp.map("/inlevel", _on_inlevel)
    try:
        srv = ThreadingOSCUDPServer(("127.0.0.1", 57121), disp)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    except OSError:
        pass  # puerto ocupado (otra instancia, p.ej. un screenshot) — sin VU, no crítico
_start_osc_in()

# configs del repo (no la ruta absoluta de Nicolás): junto a este webui.py, override por env.
CONFIG_DIR = os.path.expanduser(os.environ.get("BEACON_CONFIG_DIR")
             or os.path.join(os.path.dirname(os.path.abspath(__file__)), "configs"))
os.makedirs(CONFIG_DIR, exist_ok=True)

# Carpeta de fuentes WAV seleccionables desde la UI (aporte BEACON-sound).
SOURCES_DIR = os.path.expanduser(os.environ.get("BEACON_SOURCES_DIR", "~/REPOS/beacon-spatial/audio"))

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

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
    <title>Harmonic Beacon • Spatializer</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
      // Pátina de marca: remapea el acento (cyan→amatista) y las fuentes en TODA la UI
      // sin tocar las clases inline. Tinte violáceo, ritual + tecnología sobria (VISION.md).
      tailwind.config = { theme: { extend: {
        colors: {
          cyan:    { 300:'#c3aefc', 400:'#a98bff', 500:'#8b6cf0', 600:'#7654e4', 950:'#140e28' },
          emerald: { 300:'#8fdcc2', 400:'#5fc7a6', 500:'#329e7f', 950:'#0c241e' },
          amber:   { 300:'#e0bd7e', 400:'#cda85e', 500:'#b88e3f' },
          violet:  { 300:'#d6c3ff', 400:'#bfa3ff' }
        },
        fontFamily: {
          sans: ['Hanken Grotesk','system-ui','sans-serif'],
          mono: ['Spline Sans Mono','ui-monospace','monospace'],
          display: ['Fraunces','serif']
        }
      } } };
    </script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&amp;family=Hanken+Grotesk:wght@300;400;500;600;700&amp;family=Spline+Sans+Mono:wght@400;500&amp;display=swap');

        :root {
            --accent: #a98bff;          /* amatista, más saturado */
            --accent-soft: rgba(169,139,255,0.15);
            --gold: #cda85e;            /* realce ritual, uso escaso */
            --bg-0: #070510;
            --bg-1: #0c0918;
            --bg-2: #110d1f;
            --line: #211a36;
            --line-soft: rgba(169,139,255,0.09);
            --text: #e9e4f2;
            --muted: #837a96;
            --ease: cubic-bezier(0.22, 0.61, 0.36, 1);
        }

        body {
            font-family: 'Hanken Grotesk', system-ui, sans-serif;
            color: var(--text);
            background-color: var(--bg-0);
            background-image:
                radial-gradient(120% 80% at 50% -12%, rgba(98,68,196,0.16), transparent 58%),
                radial-gradient(90% 60% at 100% 0%, rgba(190,154,84,0.045), transparent 55%),
                linear-gradient(180deg, #08060f 0%, #050409 100%);
            background-attachment: fixed;
            -webkit-font-smoothing: antialiased;
        }
        /* grano sutil sobre toda la página */
        body::before {
            content: ""; position: fixed; inset: 0; z-index: 0; pointer-events: none;
            opacity: 0.035; mix-blend-mode: overlay;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
        }
        body > * { position: relative; z-index: 1; }

        .font-display {
            font-family: 'Fraunces', 'Georgia', serif;
            font-weight: 600;
            font-optical-sizing: auto;
            letter-spacing: 0;
        }

        .section {
            background: linear-gradient(180deg, rgba(18,14,30,0.82), rgba(10,8,18,0.82));
            border: 1px solid var(--line);
            backdrop-filter: blur(7px);
        }

        .band-card {
            background: linear-gradient(180deg, rgba(16,12,26,0.92), rgba(9,7,15,0.92));
            border: 1px solid var(--line);
            border-radius: 18px;
            transition: transform 0.35s var(--ease), border-color 0.35s var(--ease), box-shadow 0.35s var(--ease);
            /* revelado escalonado al cargar */
            opacity: 0;
            animation: cardIn 0.6s var(--ease) forwards;
        }

        .band-card:hover {
            border-color: var(--accent);
            transform: translateY(-3px);
            box-shadow: 0 10px 30px -12px rgba(125,91,230,0.45);
        }

        @keyframes cardIn {
            from { opacity: 0; transform: translateY(10px); }
            to   { opacity: 1; transform: translateY(0); }
        }
        #band-grid > .band-card:nth-child(1){animation-delay:.02s} #band-grid > .band-card:nth-child(2){animation-delay:.05s}
        #band-grid > .band-card:nth-child(3){animation-delay:.08s} #band-grid > .band-card:nth-child(4){animation-delay:.11s}
        #band-grid > .band-card:nth-child(5){animation-delay:.14s} #band-grid > .band-card:nth-child(6){animation-delay:.17s}
        #band-grid > .band-card:nth-child(7){animation-delay:.20s} #band-grid > .band-card:nth-child(8){animation-delay:.23s}
        #band-grid > .band-card:nth-child(9){animation-delay:.26s} #band-grid > .band-card:nth-child(10){animation-delay:.29s}
        #band-grid > .band-card:nth-child(11){animation-delay:.32s} #band-grid > .band-card:nth-child(12){animation-delay:.35s}
        #band-grid > .band-card:nth-child(13){animation-delay:.38s}
        .tab-panel { animation: panelIn 0.4s var(--ease) both; }
        @keyframes panelIn { from { opacity:0; transform: translateY(6px) } to { opacity:1; transform:none } }

        .slider {
            accent-color: #22d3ee;
        }

        .value-display {
            font-variant-numeric: tabular-nums;
            font-feature-settings: "tnum";
        }

        .sensor-card {
            background: #0f1117;
            border: 1px solid #1f2937;
            transition: all 0.2s ease;
        }

        .live-dot {
            animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }

        .param-pill {
            background: #1f2937;
            font-size: 0.65rem;
            padding: 1px 6px;
            border-radius: 9999px;
            font-weight: 600;
        }

        .driver-row {
            background: #11151f;
            border: 1px solid #1f2937;
            font-family: ui-monospace, monospace;
            font-size: 0.75rem;
        }

        .spectrum-bar {
            transition: height 80ms linear;
        }

        .navy {
            background: #0a0c12;
        }

        .control-label {
            font-size: 0.66rem;
            letter-spacing: 0.6px;
            font-weight: 600;
            color: #948daa;
        }

        .big-value {
            font-size: 1.1rem;
            font-weight: 600;
            font-variant-numeric: tabular-nums;
        }

        .modern-slider {
            height: 5px;
            background: linear-gradient(90deg, var(--accent-soft), rgba(255,255,255,0.04));
            border-radius: 999px;
            outline: none;
        }

        .modern-slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            height: 15px;
            width: 15px;
            background: var(--accent);
            border-radius: 999px;
            box-shadow: 0 0 0 3px var(--accent-soft), 0 0 10px -1px rgba(169,139,255,0.5);
            cursor: pointer;
            transition: box-shadow 0.2s var(--ease), transform 0.15s var(--ease);
        }
        .modern-slider::-moz-range-thumb {
            height: 15px; width: 15px; border: none;
            background: var(--accent); border-radius: 999px;
            box-shadow: 0 0 0 3px var(--accent-soft);
            cursor: pointer;
        }
        .modern-slider::-webkit-slider-thumb:hover {
            box-shadow: 0 0 0 5px var(--accent-soft), 0 0 16px 0 rgba(169,139,255,0.6);
            transform: scale(1.12);
        }
        .modern-slider:active::-webkit-slider-thumb { transform: scale(0.96); }

        .band-header {
            font-size: 0.7rem;
            font-weight: 700;
            letter-spacing: 0.5px;
        }

        .canvas-orientation {
            background: #11151f;
            border-radius: 12px;
            border: 1px solid #1f2937;
        }

        .stat {
            font-size: 0.7rem;
            color: #64748b;
        }
    </style>
</head>
<body class="text-slate-200">
    <!-- Top Bar -->
    <div class="sticky top-0 z-50 bg-[#0a0c12]/95 backdrop-blur border-b border-slate-800">
        <div class="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
            <div class="flex items-center gap-x-3">
                <div class="flex items-center gap-x-2">
                    <div class="w-8 h-8 rounded-xl bg-gradient-to-br from-cyan-400 to-teal-500 flex items-center justify-center">
                        <i class="fa-solid fa-satellite text-white text-lg"></i>
                    </div>
                    <div>
                        <div class="font-display text-3xl leading-none" style="letter-spacing:0.01em;">Beacon</div>
                        <div class="text-[9px] text-slate-500 mt-0.5" style="letter-spacing:0.28em;">HARMONIC SPATIALIZER</div>
                    </div>
                </div>
                <div class="hidden sm:block text-xs px-2.5 py-1 rounded-full bg-slate-900 border border-slate-800 text-slate-400">
                    13-band • 40Hz series
                </div>
            </div>

            <!-- (Los controles de sensores —Influence/LIVE/Permissions— viven en la pestaña Sensores) -->
            <div class="flex items-center gap-x-2 text-[10px] text-slate-500 font-mono">
                <i class="fa-solid fa-circle text-emerald-500/70 text-[7px]"></i><span>consola</span>
            </div>
        </div>
    </div>

    <div class="max-w-7xl mx-auto px-4 pb-8 pt-4">

        <!-- Tabs (Manual / Sensors / Presets) -->
        <div class="flex items-center gap-2 mb-4" id="tab-bar">
            <button data-tab-target="spatial" class="tab-btn px-4 py-2 rounded-2xl text-sm font-medium border border-slate-700 bg-slate-900 text-slate-400 hover:text-slate-200">
                <i class="fa-solid fa-circle-nodes text-xs mr-1.5"></i>Espacial
            </button>
            <button data-tab-target="manual" class="tab-btn px-4 py-2 rounded-2xl text-sm font-medium border border-cyan-500/40 bg-cyan-500/10 text-cyan-300">
                <i class="fa-solid fa-sliders text-xs mr-1.5"></i>Manual
            </button>
            <button data-tab-target="presets" class="tab-btn px-4 py-2 rounded-2xl text-sm font-medium border border-slate-700 bg-slate-900 text-slate-400 hover:text-slate-200">
                <i class="fa-solid fa-folder-open text-xs mr-1.5"></i>Presets
            </button>
            <button data-tab-target="sensors" class="tab-btn px-4 py-2 rounded-2xl text-sm font-medium border border-slate-700 bg-slate-900 text-slate-400 hover:text-slate-200 opacity-70">
                <i class="fa-solid fa-mobile-screen text-xs mr-1.5"></i>Sensores
            </button>
        </div>

        <!-- FUENTE / transporte: QUÉ suena (el engine reproduce en loop; cambiar = recarga en vivo) -->
        <div class="section rounded-2xl px-4 py-3 mb-5 flex items-center gap-4">
            <span class="w-10 h-10 rounded-xl border border-slate-700 flex items-center justify-center text-cyan-300 shrink-0 text-lg"><i class="fa-solid fa-circle-play"></i></span>
            <div class="flex-1 min-w-0 flex flex-col gap-2.5">
                <!-- fila FUENTE -->
                <div class="flex items-center gap-3 flex-wrap">
                    <span class="control-label w-12 shrink-0">FUENTE</span>
                    <div class="flex rounded-lg border border-slate-700 overflow-hidden text-xs shrink-0">
                        <button id="mode-file" onclick="setMode(0)" class="px-3 py-1 font-medium transition-colors">Archivo</button>
                        <button id="mode-live" onclick="setMode(1)" class="px-3 py-1 font-medium border-l border-slate-700 transition-colors">En vivo</button>
                    </div>
                    <div class="flex items-center gap-1.5 shrink-0" title="nivel de entrada de placa">
                        <i class="fa-solid fa-microphone text-[10px] text-slate-500"></i>
                        <div class="w-16 h-1.5 rounded-full bg-slate-800 overflow-hidden"><div id="in-vu" class="h-full transition-[width] duration-75" style="width:0%;background:#475569"></div></div>
                    </div>
                    <span id="source-now" class="font-mono text-sm text-slate-200 truncate flex-1 min-w-[80px]">—</span>
                    <select id="source-select" onchange="onSourceChange(this.value)"
                            class="bg-slate-950 border border-slate-700 rounded-xl px-3 py-1.5 text-sm text-slate-300 min-w-[210px] outline-none shrink-0">
                        <option value="">— elegí un WAV —</option>
                    </select>
                    <button onclick="onSourceRefresh()" title="refrescar lista"
                            class="w-8 h-8 rounded-xl border border-slate-700 text-slate-400 hover:bg-slate-900 hover:border-cyan-500/40 transition-colors shrink-0"><i class="fa-solid fa-arrows-rotate text-xs"></i></button>
                </div>
                <!-- fila SALIDA -->
                <div class="flex items-center gap-3 flex-wrap">
                    <span class="control-label w-12 shrink-0">SALIDA</span>
                    <i class="fa-solid fa-volume-high text-[11px] text-slate-500 shrink-0"></i>
                    <select id="output-select" onchange="setOutput(this.value)" title="dispositivo de salida"
                            class="bg-slate-950 border border-slate-700 rounded-xl px-3 py-1.5 text-sm text-slate-300 outline-none min-w-[210px] shrink-0">
                        <option value="">—</option>
                    </select>
                    <span id="source-status" class="text-[10px] text-slate-500 font-mono ml-auto truncate"></span>
                </div>
            </div>
        </div>

        <!-- Spectrum Visual (always visible) -->
        <div class="mb-5">
            <div class="flex items-end gap-1 h-16 px-1 bg-slate-950/70 border border-slate-800 rounded-3xl p-2" id="spectrum">
                {% for band in bands %}
                <div class="flex-1 flex flex-col items-center">
                    <div class="spectrum-bar w-full rounded-t-full transition-all duration-75"
                         id="spec{{ loop.index }}"
                         style="background: {{ band.color }}; height: {{ (band.default_gain / 3.0 * 100)|int }}%; min-height: 4px;"></div>
                    <div class="text-[9px] text-slate-500 mt-0.5 font-mono">{{ band.freq }}</div>
                </div>
                {% endfor %}
            </div>
        </div>

        <!-- ============= TAB: ESPACIAL ============= -->
        <section data-tab="spatial" class="tab-panel" hidden>
            <div class="flex items-center justify-between mb-2 px-1">
                <div class="flex items-center gap-x-2">
                    <span class="font-semibold tracking-tight text-lg">Campo espacial</span>
                    <span class="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-500">arrastrá los armónicos</span>
                </div>
                <span class="text-[10px] text-slate-500 font-mono">ángulo = azimut · radio = distancia · tamaño = gain</span>
            </div>
            <div class="section rounded-3xl p-5 border border-slate-800 flex flex-col lg:flex-row gap-6 items-center justify-center">
                <div class="flex flex-col items-center">
                    <canvas id="spatial-canvas" class="touch-none" style="cursor:default;"></canvas>
                    <div class="flex items-center gap-2 mt-3 text-xs text-slate-400">
                        <button onclick="spZoomBy(1/1.2)" title="alejar" class="w-7 h-7 rounded-lg border border-slate-700 hover:bg-slate-800 hover:border-cyan-500/40 transition-colors"><i class="fa-solid fa-minus text-[10px]"></i></button>
                        <span id="sp-zoom" class="font-mono w-12 text-center text-slate-300">100%</span>
                        <button onclick="spZoomBy(1.2)" title="acercar" class="w-7 h-7 rounded-lg border border-slate-700 hover:bg-slate-800 hover:border-cyan-500/40 transition-colors"><i class="fa-solid fa-plus text-[10px]"></i></button>
                        <button onclick="spResetView()" title="centrar" class="ml-1 w-7 h-7 rounded-lg border border-slate-700 hover:bg-slate-800 hover:border-cyan-500/40 transition-colors"><i class="fa-solid fa-arrows-to-dot text-[10px]"></i></button>
                    </div>
                    <div class="text-[10px] text-slate-500 mt-2">clic = seleccionar · arrastrar = mover · rueda = zoom · arrastrar vacío = desplazar</div>
                </div>
                <!-- Panel del canal seleccionado -->
                <div class="w-full lg:w-48 shrink-0 rounded-2xl border border-slate-800 bg-[#0d0a18]/60 p-4 flex flex-col gap-3">
                    <div class="control-label">CANAL SELECCIONADO</div>
                    <div id="sel-freq" class="font-mono text-2xl leading-none" style="color:#6b6480">—</div>
                    <div class="border-t border-slate-800/80 -mx-4"></div>
                    <div class="flex gap-2">
                        <button id="sel-solo" onclick="toggleSelSolo()" class="flex-1 py-1.5 rounded-xl border border-slate-700 text-xs font-bold text-slate-400 hover:bg-slate-800 transition-all">SOLO</button>
                        <button id="sel-mute" onclick="toggleSelMute()" class="flex-1 py-1.5 rounded-xl border border-slate-700 text-xs font-bold text-slate-400 hover:bg-slate-800 transition-all">MUTE</button>
                    </div>
                    <div class="flex flex-col items-center gap-2 pt-2 mt-auto">
                        <span class="control-label self-start">GANANCIA</span>
                        <input id="sel-gain" type="range" min="0" max="3" step="0.05" value="1" oninput="setSelGain(this.value)"
                               class="modern-slider" style="writing-mode: vertical-lr; direction: rtl; width:6px; height:168px;">
                        <span id="sel-gain-val" class="font-mono text-sm text-cyan-300">—</span>
                    </div>
                </div>
            </div>
        </section>

        <!-- ============= TAB: MANUAL ============= -->
        <section data-tab="manual" class="tab-panel">
            <div class="flex items-center justify-between mb-2 px-1">
                <div class="flex items-center gap-x-2">
                    <span class="font-semibold tracking-tight text-lg">Manual Controls</span>
                    <span class="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-500">13 bands</span>
                </div>
                <button onclick="resetAll()"
                        class="text-xs flex items-center gap-1.5 px-3 py-1 rounded-xl border border-orange-500/30 text-orange-400 hover:bg-orange-500/10 transition-colors">
                    <i class="fa-solid fa-undo text-xs"></i>
                    <span class="font-medium">Reset</span>
                </button>
            </div>

            <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-7 gap-2" id="band-grid">
                {% for band in bands %}
                <div class="band-card rounded-2xl p-2.5 border border-slate-800" id="band{{ loop.index }}" style="border-color: {{ band.color }}20;">
                    <div class="flex items-center justify-between mb-1.5">
                        <div>
                            <div class="band-header font-mono" style="color: {{ band.color }};">{{ band.freq }} Hz</div>
                        </div>
                        <div class="flex gap-1">
                            <button onclick="toggleMute({{ loop.index }}, this)" id="m{{ loop.index }}"
                                    class="text-[9px] px-2 py-px border border-slate-700 hover:border-slate-600 rounded-lg font-bold text-slate-400 transition-all">MUTE</button>
                            <button onclick="toggleSolo({{ loop.index }}, this)" id="s{{ loop.index }}"
                                    class="solo-btn text-[9px] px-2 py-px border border-slate-700 hover:border-slate-600 rounded-lg font-bold text-slate-400 active:bg-white active:text-black transition-all">SOLO</button>
                        </div>
                    </div>

                    <!-- Gain -->
                    <div class="mb-2">
                        <div class="flex justify-between items-baseline mb-0.5">
                            <span class="control-label">GAIN</span>
                            <span id="g{{ loop.index }}" class="value-display font-mono text-cyan-300 text-sm">{{ band.default_gain }}</span>
                        </div>
                        <input type="range" min="0" max="3" step="0.05" value="{{ band.default_gain }}" id="gain{{ loop.index }}"
                               class="modern-slider w-full accent-cyan-400"
                               oninput="send('gain', {{ loop.index }}, this.value); show(this, 'g{{ loop.index }}'); updateSpec({{ loop.index }}, this.value)">
                    </div>

                    <!-- Azimuth -->
                    <div class="mb-2">
                        <div class="flex justify-between items-baseline mb-0.5">
                            <span class="control-label">AZIMUTH</span>
                            <span id="a{{ loop.index }}" class="value-display font-mono text-amber-300 text-sm">{{ band.default_az }}°</span>
                        </div>
                        <input type="range" min="-180" max="180" step="1" value="{{ band.default_az }}" id="az{{ loop.index }}"
                               class="modern-slider w-full accent-amber-400"
                               oninput="send('az', {{ loop.index }}, this.value); show(this, 'a{{ loop.index }}')">
                    </div>

                    <!-- Distance -->
                    <div class="mb-2">
                        <div class="flex justify-between items-baseline mb-0.5">
                            <span class="control-label">DISTANCE</span>
                            <span id="d{{ loop.index }}" class="value-display font-mono text-emerald-300 text-sm">{{ band.default_dist }}</span>
                        </div>
                        <input type="range" min="0" max="10" step="0.01" value="{{ band.default_dist }}" id="dist{{ loop.index }}"
                               class="modern-slider w-full accent-emerald-400"
                               oninput="send('dist', {{ loop.index }}, this.value); show(this, 'd{{ loop.index }}')">
                    </div>

                    {% if band.default_q is defined %}
                    <!-- Q -->
                    <div>
                        <div class="flex justify-between items-baseline mb-0.5">
                            <span class="control-label">Q (resonance)</span>
                            <span id="q{{ loop.index }}" class="value-display font-mono text-violet-300 text-sm">{{ band.default_q }}</span>
                        </div>
                        <input type="range" min="0.01" max="2.0" step="0.001" value="{{ band.default_q }}" id="q{{ loop.index }}"
                               class="modern-slider w-full accent-violet-400"
                               oninput="send('q', {{ loop.index }}, this.value); show(this, 'q{{ loop.index }}')">
                    </div>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
        </section>

        <!-- ============= TAB: SENSORS ============= -->
        <section data-tab="sensors" class="tab-panel" hidden>
            <div class="flex items-center justify-between mb-3 px-1">
                <div class="flex items-center gap-x-2">
                    <span class="font-semibold tracking-tight text-lg">Sensores</span>
                    <span class="px-2 py-0.5 text-[10px] bg-teal-900/50 text-teal-400 rounded-full text-center font-medium">teléfono → parámetros (opcional)</span>
                </div>
                <div class="text-[10px] text-slate-500 font-mono" id="sensor-tab-hint">
                    modulación en vivo con el teléfono
                </div>
            </div>

            <!-- Controles de la capa de sensores (reubicados desde el top bar) -->
            <div class="section rounded-2xl p-3 mb-3 flex items-center gap-3 flex-wrap">
                <button onclick="toggleLiveSensorsUI()" id="live-btn"
                        class="flex items-center gap-x-2 px-4 py-1.5 rounded-2xl text-sm font-medium border transition-all active:scale-[0.985] bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20">
                    <i class="fa-solid fa-play text-xs"></i><span id="live-text" class="font-semibold">LIVE</span>
                </button>
                <div class="flex items-center gap-x-2 bg-slate-950 border border-slate-700 rounded-2xl px-3 py-1.5">
                    <span class="control-label">INFLUENCE</span>
                    <input type="range" id="sensor-influence" class="w-28 accent-cyan-400" min="0" max="1" step="0.01" value="0.65" oninput="updateSensorInfluence(this.value)">
                    <span id="influence-val" class="font-mono text-sm text-cyan-300 w-8 text-right">0.65</span>
                </div>
                <button onclick="requestSensorPermissions()"
                        class="flex items-center gap-x-2 px-3 py-1.5 text-xs font-medium rounded-2xl border border-slate-700 hover:bg-slate-900 transition-colors">
                    <i class="fa-solid fa-mobile-screen-button"></i><span>Permisos</span>
                </button>
                <span id="sensor-status" class="text-[10px] text-slate-500 font-mono ml-auto">en pausa</span>
            </div>

            <div class="section rounded-3xl p-4 border border-slate-800">

                <!-- Orientation Visual -->
                <div class="mb-4">
                    <div class="flex justify-between items-center mb-1.5 px-1">
                        <span class="control-label">ORIENTATION VISUAL</span>
                        <span id="orientation-label" class="text-[10px] text-slate-500 font-mono">—</span>
                    </div>
                    <canvas id="orientation-canvas" width="300" height="140" class="canvas-orientation w-full"></canvas>
                </div>

                <!-- Sensor Cards -->
                <div class="grid grid-cols-2 gap-3 mb-4" id="sensor-cards">
                    <!-- Populated by JS: Yaw, Pitch, Roll, Accel -->
                </div>

                <!-- Mapping Editor -->
                <div class="mb-3">
                    <div class="flex items-center justify-between mb-1.5 px-0.5">
                        <span class="control-label">MAPPING EDITOR</span>
                        <button onclick="resetSensorMappingToDefault(); buildSensorMappingUI(); updateDebugViz();"
                                class="text-[10px] px-2 py-0.5 rounded-lg border border-slate-700 hover:bg-slate-900 text-slate-400">Reset defaults</button>
                    </div>

                    <div id="sensor-mapping-rows" class="space-y-2 text-sm">
                        <!-- JS populated beautiful rows -->
                    </div>
                </div>

                <!-- Active Drivers -->
                <div>
                    <div class="flex items-center justify-between mb-1.5 px-0.5">
                        <span class="control-label">CURRENTLY DRIVING</span>
                        <button onclick="applyCurrentMappingAndSend()"
                                class="text-emerald-400 hover:text-emerald-300 text-xs flex items-center gap-1 px-2 py-0.5 rounded-lg border border-emerald-900 hover:bg-emerald-950">
                            <i class="fa-solid fa-paper-plane text-xs"></i>
                            <span class="font-medium text-[10px]">FORCE SEND</span>
                        </button>
                    </div>
                    <div id="sensor-driving"
                         class="bg-[#0a0c12] border border-slate-800 rounded-2xl p-3 min-h-[68px] text-xs font-mono leading-snug text-emerald-300/90 whitespace-pre-line">
                        (enable LIVE and move your phone)
                    </div>
                </div>

                <!-- Sensor Debug Panel (visible, no DevTools needed) -->
                <div class="mt-4 border-t border-slate-800 pt-3">
                    <div class="flex items-center justify-between mb-1.5 px-0.5">
                        <span class="control-label">SENSOR DEBUG</span>
                        <button onclick="updateSensorDebugPanel()"
                                class="text-[10px] px-2 py-0.5 rounded-lg border border-slate-700 hover:bg-slate-900 text-slate-400">Refresh</button>
                    </div>
                    <div id="sensor-debug-panel"
                         class="bg-[#0a0c12] border border-slate-800 rounded-2xl p-3 text-[10px] font-mono leading-relaxed text-slate-400 space-y-0.5">
                        <!-- JS populated -->
                    </div>
                    <div class="text-[9px] text-slate-500 mt-1 px-0.5 leading-relaxed">
                        Shows: browser support, last event timestamps, listener state, fetch count, errors. Tap Refresh to update.
                    </div>
                </div>

                <div class="flex flex-wrap gap-2 mt-3 text-xs">
                    <button onclick="recenterSensors()"
                            title="Set the current phone pose as the new 'center' / neutral position. Subsequent rotations are measured relative to this point."
                            class="flex-1 sm:flex-none px-3 py-1.5 bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 rounded-2xl text-cyan-400 text-xs font-medium flex items-center justify-center gap-2">
                        <i class="fa-solid fa-crosshairs"></i> <span>Recenter</span>
                    </button>
                    <button onclick="saveSensorConfigToPreset()"
                            class="flex-1 sm:flex-none px-3 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-2xl text-emerald-400 text-xs font-medium flex items-center justify-center gap-2">
                        <i class="fa-solid fa-save"></i> <span>Save mapping to preset</span>
                    </button>
                    <button onclick="exportSensorConfig()"
                            class="flex-1 sm:flex-none px-3 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-2xl text-xs font-medium flex items-center justify-center gap-2">
                        <i class="fa-solid fa-download"></i> <span>Export JSON</span>
                    </button>
                </div>
            </div>
        </section>

        <!-- ============= TAB: PRESETS ============= -->
        <section data-tab="presets" class="tab-panel" hidden>
            <div class="flex items-center justify-between mb-3 px-1">
                <div class="flex items-center gap-x-2">
                    <span class="font-semibold tracking-tight text-lg">Presets</span>
                    <span id="preset-count" class="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-500">0 files</span>
                </div>
                <button onclick="loadConfigList()"
                        class="text-xs flex items-center gap-1.5 px-3 py-1 rounded-xl border border-slate-700 text-slate-400 hover:bg-slate-900">
                    <i class="fa-solid fa-arrows-rotate text-xs"></i>
                    <span class="font-medium">Refresh</span>
                </button>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <!-- Save panel -->
                <div class="section rounded-3xl p-4 border border-slate-800">
                    <div class="control-label mb-2">SAVE CURRENT STATE</div>
                    <input id="save-name" type="text" placeholder="preset name"
                           class="w-full bg-slate-950 border border-slate-700 rounded-2xl px-3 py-2 text-sm outline-none text-slate-300 placeholder:text-slate-600 mb-3">
                    <button onclick="saveConfig()"
                            class="w-full py-2 rounded-2xl border border-emerald-500/40 text-emerald-400 hover:bg-emerald-950 font-medium text-sm flex items-center justify-center gap-2">
                        <i class="fa-solid fa-save text-xs"></i>
                        <span>Save (bands + mix + master + sensor_mappings)</span>
                    </button>
                    <div class="text-[10px] text-slate-500 mt-2 leading-relaxed">
                        Includes the current <span class="font-mono text-slate-400">sensor_mappings</span> from the Sensors tab so a preset can be loaded on any device with the same mapping intact.
                    </div>
                </div>

                <!-- Load panel -->
                <div class="section rounded-3xl p-4 border border-slate-800">
                    <div class="flex items-center justify-between mb-2">
                        <span class="control-label">LOAD FROM DISK</span>
                    </div>
                    <select id="load-select-large"
                            class="w-full bg-slate-950 border border-slate-700 rounded-2xl px-3 py-2 text-sm outline-none text-slate-300 mb-3">
                        <option value="">— pick a preset —</option>
                    </select>
                    <button onclick="loadConfigFromLargeSelect()"
                            class="w-full py-2 rounded-2xl border border-cyan-500/40 text-cyan-400 hover:bg-cyan-950 font-medium text-sm flex items-center justify-center gap-2">
                        <i class="fa-solid fa-download text-xs"></i>
                        <span>Load preset</span>
                    </button>
                </div>
            </div>

            <!-- Preset list (visible, clickable cards) -->
            <div class="mt-4">
                <div class="control-label mb-2 px-1">FILES IN configs/</div>
                <div id="preset-cards" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                    <!-- JS populated from /list_configs -->
                </div>
            </div>
        </section>

        <!-- Global Mix & Master -->
        <div class="mt-5 section rounded-3xl p-4 border border-slate-800">
            <div class="grid grid-cols-1 md:grid-cols-4 gap-5">
                <!-- Mix -->
                <div>
                    <div class="flex justify-between items-center mb-1">
                        <span class="font-semibold text-sm tracking-tight">MIX (wet)</span>
                        <span id="vmix" class="font-mono text-cyan-300">0.85</span>
                    </div>
                    <input type="range" min="0" max="1" step="0.01" value="0.85" id="mix"
                           class="modern-slider w-full accent-cyan-400"
                           oninput="sendGlobal('mix', this.value); show(this, 'vmix')">
                </div>
                
                <!-- Master -->
                <div>
                    <div class="flex justify-between items-center mb-1">
                        <span class="font-semibold text-sm tracking-tight">MASTER</span>
                        <span id="vmaster" class="font-mono text-cyan-300">0.90</span>
                    </div>
                    <input type="range" min="0" max="2" step="0.01" value="0.9" id="master"
                           class="modern-slider w-full accent-cyan-400"
                           oninput="sendGlobal('master', this.value); show(this, 'vmaster')">
                </div>

                <!-- Record -->
                <div>
                    <div class="flex justify-between items-center mb-1">
                        <span class="font-semibold text-sm tracking-tight text-red-400">RECORD</span>
                    </div>
                    <button id="rec-btn" onclick="toggleRecord(this)"
                            class="w-full py-2 rounded-2xl border border-red-500/40 text-red-400 hover:bg-red-950 font-medium text-sm flex items-center justify-center gap-2">
                        <i class="fa-solid fa-circle"></i>
                        <span>START</span>
                    </button>
                </div>

                <!-- Reset All -->
                <div>
                    <div class="flex justify-between items-center mb-1">
                        <span class="font-semibold text-sm tracking-tight">GLOBAL</span>
                    </div>
                    <button onclick="resetAll()"
                            class="w-full py-2 rounded-2xl border border-orange-500/30 text-orange-400 hover:bg-orange-950 font-medium text-sm flex items-center justify-center gap-2">
                        <i class="fa-solid fa-undo"></i>
                        <span>RESET ALL</span>
                    </button>
                </div>
            </div>
        </div>

        <div class="text-center mt-6 text-[10px] text-slate-600">
            Phone sensors → live modulation • Works on iOS Safari &amp; Android Chrome • Send feedback to the Beacon
        </div>

    </div>

    <script>
        // Tailwind script
        function initTailwind() {
            document.documentElement.style.setProperty('--accent', '#a98bff');
        }

        // Keep all the original logic + enhance for new UI
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
        
        // === SOURCE (WAV) selection (aporte BEACON-sound) ===
        async function loadSources() {
            const sel = document.getElementById('source-select');
            const st = document.getElementById('source-status');
            const now = document.getElementById('source-now');
            try {
                const r = await fetch('/list_sources');
                const j = await r.json();
                const list = j.sources || [];
                sel.innerHTML = '<option value="">— elegí un WAV —</option>';
                list.forEach(s => {
                    const o = document.createElement('option');
                    o.value = s.path; o.textContent = s.name;
                    if (s.name === j.playing) o.selected = true;   // refleja lo que el engine ya está reproduciendo
                    sel.appendChild(o);
                });
                window.__playingName = j.playing || '—';
                if (now && beaconMode === 0) now.textContent = j.playing || '—';
                if (st) st.textContent = list.length + ' archivos · cambiar = recarga en vivo';
            } catch (e) { if (st) st.textContent = 'error listando fuentes'; }
        }
        function selectSource(path) {
            if (!path) return;
            const st = document.getElementById('source-status');
            const now = document.getElementById('source-now');
            const name = path.split('/').pop();
            fetch('/source', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({path: path})
            }).then(r => r.json()).then(j => {
                if (j.ok) { window.__playingName = name; highlightMode(0);   // cargar un archivo = volver a modo archivo
                            if (now) now.textContent = name; if (st) st.textContent = '▸ ' + name; }
                else if (st) st.textContent = '✗ ' + (j.error||'');
            }).catch(() => { if (st) st.textContent = '✗ error'; });
        }
        // Modo de fuente: 0 = archivo (loop del WAV), 1 = entrada de placa (vivo)
        let beaconMode = 0;
        function highlightMode(m){ beaconMode = m;
            const f=document.getElementById('mode-file'), l=document.getElementById('mode-live');
            if(f&&l){
                f.classList.toggle('bg-cyan-500/20', m===0); f.classList.toggle('text-cyan-300', m===0); f.classList.toggle('text-slate-400', m!==0);
                l.classList.toggle('bg-emerald-500/20', m===1); l.classList.toggle('text-emerald-300', m===1); l.classList.toggle('text-slate-400', m!==1);
            }
            // el dropdown muestra WAVs (archivo) o entradas de captura (vivo)
            if(m===1) loadInputs(); else loadSources();
        }
        function setMode(m){ highlightMode(m);
            fetch('/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({address:'/beacon/mode',value:m})}).catch(()=>{});
        }
        function onSourceChange(v){ if(beaconMode===1) selectInput(v); else selectSource(v); }
        function onSourceRefresh(){ if(beaconMode===1) loadInputs(); else loadSources(); }
        // Modo vivo: entradas de captura
        async function loadInputs(){ const sel=document.getElementById('source-select'); const now=document.getElementById('source-now'); const st=document.getElementById('source-status'); if(!sel) return;
            try{ const j=await (await fetch('/list_inputs')).json(); const list=j.inputs||[];
                sel.innerHTML = '<option value="">— elegí una entrada —</option>';
                let curLabel='entrada de placa';
                list.forEach(o=>{ const op=document.createElement('option'); op.value=o.node; op.textContent=o.label;
                    if(o.node===j.current){ op.selected=true; curLabel=o.label; } sel.appendChild(op); });
                if(now) now.textContent = curLabel;
                if(st) st.textContent = list.length + ' entradas · en vivo por la placa';
            }catch(e){ if(st) st.textContent='error listando entradas'; }
        }
        function selectInput(node){ if(!node) return; const st=document.getElementById('source-status'); const now=document.getElementById('source-now');
            fetch('/input',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({node:node})})
              .then(r=>r.json()).then(j=>{ if(j.ok){ if(now) now.textContent=j.label||''; if(st) st.textContent='entrada → '+(j.label||''); } else if(st) st.textContent='✗ '+(j.error||''); }).catch(()=>{ if(st) st.textContent='✗ error'; });
        }
        window.addEventListener('load', loadSources);
        window.addEventListener('load', () => highlightMode(0));
        // Salida seleccionable (re-ruteo pw-link en el server)
        async function loadOutputs(){ const sel=document.getElementById('output-select'); if(!sel) return;
            try{ const j=await (await fetch('/list_outputs')).json(); const list=j.outputs||[];
                sel.innerHTML = '<option value="">—</option>';
                list.forEach(o=>{ const op=document.createElement('option'); op.value=o.node; op.textContent=o.label;
                    if(o.node===j.current) op.selected=true;   // preseleccionar la salida activa
                    sel.appendChild(op); });
            }catch(e){}
        }
        function setOutput(node){ if(!node) return; const st=document.getElementById('source-status');
            fetch('/output',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({node:node})})
              .then(r=>r.json()).then(j=>{ if(st) st.textContent = j.ok ? ('salida → '+(j.label||'')) : ('✗ '+(j.error||'')); }).catch(()=>{ if(st) st.textContent='✗ error salida'; });
        }
        window.addEventListener('load', loadOutputs);
        // VU de entrada: poll a /level (lo alimenta sclang vía OSC) → barra
        function pollLevel(){
            fetch('/level').then(r=>r.json()).then(j=>{
                const v=Math.max(0, j.level||0); const el=document.getElementById('in-vu'); if(!el) return;
                const pct=Math.min(100, Math.round(Math.sqrt(Math.min(v,1))*118));
                el.style.width=pct+'%';
                el.style.background = pct>88 ? '#f43f5e' : (pct>4 ? '#34d399' : '#475569');
            }).catch(()=>{});
        }
        setInterval(pollLevel, 100);

        // === Campo espacial — radar HiDPI, nodos con halo, declutter de clusters ===
        const SP = { size:440, cx:220, cy:220, Rmax:188, Dmax:5, gamma:0.4 };  // gamma<1 = más detalle cerca del centro (más bajo = más exponencial)
        const bandColors = ["#c0392b","#e67e22","#f1c40f","#2ecc71","#1abc9c","#3498db","#2980b9","#8e44ad","#9b59b6","#e84393","#fd79a8","#a29bfe","#dfe6e9"];
        const freqLabels = ["40","80","120","160","200","240","480","720","960","1200","1440","1680","1800+"];
        let spatialActive=false, selectedBand=0, hoverBand=0, spDragging=false, spPanning=false, lastSpSend=0, spNodes=[];
        let spView={zoom:1,panx:0,pany:0}, panLast=[0,0];
        let grabPx0=0, grabPy0=0, grabTx0=0, grabTy0=0, spMoved=false;   // grab relativo: clic no altera
        let mutedState=[0,0,0,0,0,0,0,0,0,0,0,0,0], prevGain=[null,null,null,null,null,null,null,null,null,null,null,null,null];

        function spVal(id){ const e=document.getElementById(id); return e?parseFloat(e.value):0; }
        function spShade(hex,amt){ const n=parseInt(hex.slice(1),16);
            const r=Math.max(0,Math.min(255,(n>>16)+amt)), g=Math.max(0,Math.min(255,((n>>8)&255)+amt)), b=Math.max(0,Math.min(255,(n&255)+amt));
            return 'rgb('+r+','+g+','+b+')'; }
        // escala radial no-lineal (gamma<1): más detalle cerca del centro
        function distToR(d){ return Math.pow(Math.min(d/SP.Dmax,1.12), SP.gamma)*SP.Rmax; }
        function rToDist(r){ return Math.pow(Math.min(r/SP.Rmax,1), 1/SP.gamma)*SP.Dmax; }
        function azDistToXY(a,d){ const r=distToR(d), th=(-90-a)*Math.PI/180;
            return [SP.cx+r*Math.cos(th), SP.cy+r*Math.sin(th)]; }
        function xyToAzDist(mx,my){ const dx=mx-SP.cx, dy=my-SP.cy;
            let d=rToDist(Math.sqrt(dx*dx+dy*dy)); d=Math.max(0,Math.min(10,d));
            let a=-90-Math.atan2(dy,dx)*180/Math.PI; while(a>180)a-=360; while(a<-180)a+=360;
            return [Math.round(a), Math.round(d*100)/100]; }   // paso de distancia fino (0.01) → sin escalones gruesos
        function spSetupCanvas(){ const c=document.getElementById('spatial-canvas'); if(!c) return;
            const dpr=window.devicePixelRatio||1;
            c.style.width=SP.size+'px'; c.style.height=SP.size+'px';
            c.width=Math.round(SP.size*dpr); c.height=Math.round(SP.size*dpr);
            c.getContext('2d').setTransform(dpr,0,0,dpr,0,0); }
        function spComputeNodes(){
            const base=[];
            for(let i=1;i<=13;i++){ const g=spVal('gain'+i),a=spVal('az'+i),d=spVal('dist'+i);
                const p=azDistToXY(a,d); base.push({i:i,g:g,x:p[0],y:p[1],rr:5+(g/3)*12}); }
            const used={}, nodes=[];
            for(let k=0;k<base.length;k++){ const bk=base[k]; if(used[bk.i])continue;
                const cl=[bk]; used[bk.i]=true;
                for(let j=k+1;j<base.length;j++){ const bj=base[j]; if(used[bj.i])continue;
                    if(Math.hypot(bk.x-bj.x,bk.y-bj.y)<13){ cl.push(bj); used[bj.i]=true; } }
                if(cl.length===1){ nodes.push(Object.assign({},bk,{dx:bk.x,dy:bk.y,fan:false})); }
                else { const ccx=cl.reduce((s,n)=>s+n.x,0)/cl.length, ccy=cl.reduce((s,n)=>s+n.y,0)/cl.length, R=18+cl.length*4.8;
                    cl.forEach((n,idx)=>{ const ang=-Math.PI/2+idx/cl.length*2*Math.PI;
                        nodes.push(Object.assign({},n,{dx:ccx+R*Math.cos(ang),dy:ccy+R*Math.sin(ang),cx0:ccx,cy0:ccy,fan:true})); }); }
            }
            spNodes=nodes;
        }
        function drawSpatial(){
            const c=document.getElementById('spatial-canvas'); if(!c) return;
            const ctx=c.getContext('2d'); const cx=SP.cx,cy=SP.cy,R=SP.Rmax, TAU=6.28319;
            const dpr=window.devicePixelRatio||1; ctx.setTransform(dpr,0,0,dpr,0,0);
            ctx.clearRect(0,0,SP.size,SP.size);
            ctx.save();
            ctx.translate(spView.panx, spView.pany);
            ctx.translate(cx,cy); ctx.scale(spView.zoom, spView.zoom); ctx.translate(-cx,-cy);
            let bg=ctx.createRadialGradient(cx,cy,0,cx,cy,R);
            bg.addColorStop(0,'rgba(40,27,72,0.50)'); bg.addColorStop(0.72,'rgba(16,11,28,0.28)'); bg.addColorStop(1,'rgba(8,6,14,0)');
            ctx.fillStyle=bg; ctx.beginPath(); ctx.arc(cx,cy,R,0,TAU); ctx.fill();
            ctx.lineWidth=1;
            [0.25,0.5,1,2,3,4].forEach(dv=>{ const rr=distToR(dv); ctx.strokeStyle='rgba(169,139,255,0.11)';
                ctx.beginPath(); ctx.arc(cx,cy,rr,0,TAU); ctx.stroke();
                ctx.fillStyle='rgba(150,140,180,0.4)'; ctx.font='8px "Spline Sans Mono",monospace'; ctx.textAlign='left';
                ctx.fillText(dv, cx+2, cy-rr-2); });
            ctx.strokeStyle='rgba(169,139,255,0.06)';
            for(let dg=0;dg<360;dg+=30){ const th=dg*Math.PI/180; ctx.beginPath(); ctx.moveTo(cx,cy); ctx.lineTo(cx+R*Math.cos(th),cy+R*Math.sin(th)); ctx.stroke(); }
            ctx.fillStyle='rgba(190,180,212,0.55)'; ctx.font='11px "Spline Sans Mono",ui-monospace,monospace';
            ctx.textAlign='center'; ctx.fillText('frente',cx,cy-R-9); ctx.fillText('atrás',cx,cy+R+19);
            ctx.textAlign='left'; ctx.fillText('der',cx+R+7,cy+4); ctx.textAlign='right'; ctx.fillText('izq',cx-R-7,cy+4);
            let lc=ctx.createRadialGradient(cx,cy,0,cx,cy,10); lc.addColorStop(0,'rgba(205,168,94,0.8)'); lc.addColorStop(1,'rgba(205,168,94,0)');
            ctx.fillStyle=lc; ctx.beginPath(); ctx.arc(cx,cy,10,0,TAU); ctx.fill();
            ctx.fillStyle='#cda85e'; ctx.beginPath(); ctx.arc(cx,cy,2.6,0,TAU); ctx.fill();
            spComputeNodes();
            const anySolo=soloState.some(s=>s);
            spNodes.forEach(n=>{ if(n.fan){ ctx.strokeStyle='rgba(169,139,255,0.28)'; ctx.lineWidth=1; ctx.setLineDash([2,3]); ctx.beginPath(); ctx.moveTo(n.cx0,n.cy0); ctx.lineTo(n.dx,n.dy); ctx.stroke(); ctx.setLineDash([]); } });
            spNodes.forEach(n=>{ const sel=(n.i===selectedBand), hov=(n.i===hoverBand), col=bandColors[n.i-1];
                ctx.globalAlpha=(anySolo&&!soloState[n.i-1])?0.25:1;
                ctx.shadowColor=col; ctx.shadowBlur=sel?24:(hov?16:9);
                const g=ctx.createRadialGradient(n.dx-n.rr*0.3,n.dy-n.rr*0.3,0,n.dx,n.dy,n.rr);
                g.addColorStop(0,spShade(col,45)); g.addColorStop(1,spShade(col,-36));
                ctx.fillStyle=g; ctx.beginPath(); ctx.arc(n.dx,n.dy,n.rr,0,TAU); ctx.fill();
                ctx.shadowBlur=0;
                ctx.strokeStyle=sel?'#fff':'rgba(255,255,255,0.4)'; ctx.lineWidth=sel?2:1;
                ctx.beginPath(); ctx.arc(n.dx,n.dy,n.rr,0,TAU); ctx.stroke();
                ctx.globalAlpha=1;
            });
            ctx.restore();
            const z=document.getElementById('sp-zoom'); if(z) z.textContent=Math.round(spView.zoom*100)+'%';
            const act=hoverBand||selectedBand;
            if(act){ const a=spVal('az'+act),d=spVal('dist'+act),g=spVal('gain'+act);
                ctx.textAlign='left'; ctx.font='13px "Spline Sans Mono",ui-monospace,monospace'; ctx.fillStyle=bandColors[act-1];
                ctx.fillText(freqLabels[act-1]+' Hz', 12, 22);
                ctx.fillStyle='rgba(200,193,220,0.7)'; ctx.font='10px "Spline Sans Mono",ui-monospace,monospace';
                ctx.fillText('az '+Math.round(a)+'°   dist '+d.toFixed(2)+'   gain '+g.toFixed(2), 12, 38);
            }
        }
        function spatialTick(){ if(!spatialActive) return; drawSpatial(); syncSelPanel(); requestAnimationFrame(spatialTick); }
        function spScreen(e){ const c=document.getElementById('spatial-canvas'); const r=c.getBoundingClientRect();
            return [(e.clientX-r.left)*(SP.size/r.width), (e.clientY-r.top)*(SP.size/r.height)]; }
        function spWorld(sx,sy){ return [(sx-spView.panx-SP.cx)/spView.zoom+SP.cx, (sy-spView.pany-SP.cy)/spView.zoom+SP.cy]; }
        function spZoomBy(f){ spView.zoom=Math.max(0.6,Math.min(5,spView.zoom*f)); }
        function spResetView(){ spView.zoom=1; spView.panx=0; spView.pany=0; }
        function updateSpectrum(){ const anySolo=soloState.some(s=>s);
            for(let i=1;i<=13;i++){ const bar=document.getElementById('spec'+i); if(!bar)continue;
                const g=spVal('gain'+i); bar.style.height=Math.max(3,(g/3)*54)+'px';   // px: el contenedor no fija altura → % no resolvía
                bar.style.opacity=(anySolo&&!soloState[i-1])?'0.22':'0.95'; } }
        function uiTick(){ updateSpectrum(); requestAnimationFrame(uiTick); }
        function spHit(mx,my){ let best=0,bestd=1e9; spNodes.forEach(n=>{ const dd=Math.hypot(mx-n.dx,my-n.dy); const t=Math.max(18,n.rr+6); if(dd<t&&dd<bestd){bestd=dd;best=n.i;} }); return best; }
        function spSend(i,a,d,force){ const now=Date.now(); if(!force&&now-lastSpSend<45)return; lastSpSend=now;
            fetch('/control/batch',{method:'POST',headers:{'Content-Type':'application/json'},
              body:JSON.stringify({updates:[{address:'/beacon/az/'+i,value:a},{address:'/beacon/dist/'+i,value:d}]}),keepalive:true}).catch(()=>{}); }
        function spApply(i,a,d,force){ const az=document.getElementById('az'+i),di=document.getElementById('dist'+i);
            if(az){az.value=a;show(az,'a'+i);} if(di){di.value=d;show(di,'d'+i);} spSend(i,a,d,force); }
        // Mute por canal (client-side: guarda el gain previo y lo pone en 0; restaura al desmutear)
        function toggleMute(i, btn){ const g=document.getElementById('gain'+i); if(!g) return;
            mutedState[i-1]=mutedState[i-1]?0:1;
            if(mutedState[i-1]){ prevGain[i-1]=parseFloat(g.value); g.value=0; }
            else { g.value=(prevGain[i-1]!=null?prevGain[i-1]:1); }
            send('gain', i, parseFloat(g.value)); show(g,'g'+i); updateSpec(i, g.value);
            const mb=btn||document.getElementById('m'+i);
            if(mb){ mb.classList.toggle('!bg-rose-500/80', !!mutedState[i-1]); mb.classList.toggle('!text-white', !!mutedState[i-1]); mb.classList.toggle('!border-rose-500/60', !!mutedState[i-1]); }
            syncSelPanel();
        }
        // Panel del canal seleccionado en el Espacial (Solo/Mute/Ganancia)
        function syncSelPanel(){
            const i=selectedBand, freqEl=document.getElementById('sel-freq');
            if(!freqEl) return;
            const soloB=document.getElementById('sel-solo'), muteB=document.getElementById('sel-mute'),
                  gEl=document.getElementById('sel-gain'), gv=document.getElementById('sel-gain-val');
            if(!i){ freqEl.textContent='—'; freqEl.style.color='#6b6480'; if(gv) gv.textContent=''; return; }
            freqEl.textContent=freqLabels[i-1]+' Hz'; freqEl.style.color=bandColors[i-1];
            const g=spVal('gain'+i); if(gEl && document.activeElement!==gEl) gEl.value=g; if(gv) gv.textContent=g.toFixed(2);
            if(soloB){ const on=!!soloState[i-1]; soloB.classList.toggle('!bg-white',on); soloB.classList.toggle('!text-black',on); }
            if(muteB){ const on=!!mutedState[i-1]; muteB.classList.toggle('!bg-rose-500/80',on); muteB.classList.toggle('!text-white',on); }
        }
        function toggleSelSolo(){ if(selectedBand){ toggleSolo(selectedBand, document.getElementById('s'+selectedBand)); syncSelPanel(); } }
        function toggleSelMute(){ if(selectedBand){ toggleMute(selectedBand, document.getElementById('m'+selectedBand)); } }
        function setSelGain(v){ if(!selectedBand) return; const i=selectedBand, g=document.getElementById('gain'+i);
            if(g){ g.value=v; show(g,'g'+i); } send('gain',i,parseFloat(v)); updateSpec(i,v);
            const gv=document.getElementById('sel-gain-val'); if(gv) gv.textContent=parseFloat(v).toFixed(2);
            if(mutedState[i-1]){ mutedState[i-1]=0; const mb=document.getElementById('m'+i); if(mb) mb.classList.remove('!bg-rose-500/80','!text-white','!border-rose-500/60'); }
        }
        function initSpatial(){ const c=document.getElementById('spatial-canvas'); if(!c) return; spSetupCanvas();
            c.addEventListener('pointerdown',ev=>{ const s=spScreen(ev); const w=spWorld(s[0],s[1]); const i=spHit(w[0],w[1]);
                c.setPointerCapture(ev.pointerId);
                if(i){ // SELECCIONAR sin mover: guardamos el punto de agarre y la posición REAL del dot
                    selectedBand=i; spDragging=true; spMoved=false; c.style.cursor='grabbing';
                    grabPx0=w[0]; grabPy0=w[1]; const t=azDistToXY(spVal('az'+i),spVal('dist'+i)); grabTx0=t[0]; grabTy0=t[1];
                    syncSelPanel(); }
                else { spPanning=true; panLast=s; c.style.cursor='move'; } });
            c.addEventListener('pointermove',ev=>{ const s=spScreen(ev);
                if(spDragging&&selectedBand){ const w=spWorld(s[0],s[1]); spMoved=true;   // mover RELATIVO a la posición real (sin teletransporte)
                    const ad=xyToAzDist(grabTx0+(w[0]-grabPx0), grabTy0+(w[1]-grabPy0)); spApply(selectedBand,ad[0],ad[1],false); }
                else if(spPanning){ spView.panx+=s[0]-panLast[0]; spView.pany+=s[1]-panLast[1]; panLast=s; }
                else { const w=spWorld(s[0],s[1]); hoverBand=spHit(w[0],w[1]); c.style.cursor=hoverBand?'grab':'default'; } });
            const end=ev=>{ if(spDragging&&selectedBand&&spMoved){ const s=spScreen(ev); const w=spWorld(s[0],s[1]);
                    const ad=xyToAzDist(grabTx0+(w[0]-grabPx0), grabTy0+(w[1]-grabPy0)); spApply(selectedBand,ad[0],ad[1],true);}
                spDragging=false; spPanning=false; c.style.cursor='default'; };
            c.addEventListener('pointerup',end); c.addEventListener('pointercancel',end);
            c.addEventListener('pointerleave',()=>{ if(!spDragging&&!spPanning) hoverBand=0; });
            c.addEventListener('wheel',ev=>{ ev.preventDefault(); const s=spScreen(ev); const w=spWorld(s[0],s[1]);
                const f=ev.deltaY<0?1.12:1/1.12; spView.zoom=Math.max(0.6,Math.min(5,spView.zoom*f));
                spView.panx=s[0]-((w[0]-SP.cx)*spView.zoom+SP.cx); spView.pany=s[1]-((w[1]-SP.cy)*spView.zoom+SP.cy); }, {passive:false});
        }

        function sendGlobal(param, value) {
            fetch('/control', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({address: '/beacon/' + param, value: parseFloat(value)})
            });
        }
        
        function show(el, id) {
            const unit = id.startsWith('a') ? '°' : '';
            const target = document.getElementById(id);
            if (target) target.textContent = parseFloat(el.value).toFixed( id.startsWith('q') ? 3 : 2 ) + unit;
        }
        
        function updateSpec(band, value) {
            const bar = document.getElementById('spec' + band);
            if (bar) bar.style.height = (parseFloat(value) / 3.0 * 100) + '%';
        }

        let recording = false;
        function toggleRecord(btn) {
            recording = !recording;
            const span = btn.querySelector('span') || btn;
            
            if (recording) {
                const label = 'session_' + new Date().toISOString().slice(0,19).replace(/[:T]/g,'-');
                sendGlobal('record/start', label);
                btn.classList.add('!bg-red-600', '!border-red-600', '!text-white');
                span.textContent = 'STOP';
            } else {
                sendGlobal('record/stop', 0);
                btn.classList.remove('!bg-red-600', '!border-red-600', '!text-white');
                span.textContent = 'START';
            }
        }

        const soloState = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
        
        function toggleSolo(band, btn) {
            soloState[band - 1] = soloState[band - 1] ? 0 : 1;
            const isActive = soloState[band - 1];
            btn.classList.toggle('!bg-white', isActive);
            btn.classList.toggle('!text-black', isActive);
            btn.classList.toggle('!border-white', isActive);
            
            send('solo', band, isActive ? 1 : 0);
            
            const anySolo = soloState.some(s => s === 1);
            for (let i = 1; i <= 13; i++) {
                const card = document.getElementById('band' + i);
                if (card) {
                    if (anySolo && !soloState[i - 1]) {
                        card.style.opacity = '0.35';
                    } else {
                        card.style.opacity = '1';
                    }
                }
            }
        }

        function resetAll() {
            sendGlobal('reset', 1);
            
            for (let i = 1; i <= 13; i++) {
                const g = document.getElementById('gain' + i);
                const a = document.getElementById('az' + i);
                const d = document.getElementById('dist' + i);
                const q = document.getElementById('q' + i);
                const s = document.getElementById('s' + i);
                
                if (g) { g.value = defaults.gains[i-1]; show(g, 'g'+i); updateSpec(i, g.value); }
                if (a) { a.value = defaults.azs[i-1]; show(a, 'a'+i); }
                if (d) { d.value = defaults.dists[i-1]; show(d, 'd'+i); }
                if (q && defaults.qs[i-1]) { q.value = defaults.qs[i-1]; show(q, 'q'+i); }
                if (s && soloState[i-1]) { toggleSolo(i, s); }
            }
            
            const mix = document.getElementById('mix');
            const master = document.getElementById('master');
            if (mix) { mix.value = defaults.mix; show(mix, 'vmix'); }
            if (master) { master.value = defaults.master; show(master, 'vmaster'); }
            
            const status = document.getElementById('config-status');
            if (status) {
                status.textContent = 'Reset to defaults';
                setTimeout(() => status.textContent = 'Presets ready', 1400);
            }
        }

        function gatherState() {
            const state = { 
                bands: [], 
                mix: parseFloat(document.getElementById('mix').value), 
                master: parseFloat(document.getElementById('master').value),
                sensor_mappings: getCurrentSensorMappings()
            };
            for (let i = 1; i <= 13; i++) {
                const b = { 
                    gain: parseFloat(document.getElementById('gain'+i).value), 
                    az: parseFloat(document.getElementById('az'+i).value), 
                    dist: parseFloat(document.getElementById('dist'+i).value), 
                    solo: soloState[i-1] 
                };
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
            if (mix) { mix.value = state.mix; sendGlobal('mix', state.mix); show(mix, 'vmix'); }
            if (master) { master.value = state.master; sendGlobal('master', state.master); show(master, 'vmaster'); }

            if (state.sensor_mappings) {
                const ta = document.getElementById('sensor-mapping-json');
                if (ta) {
                    ta.value = JSON.stringify(state.sensor_mappings, null, 2);
                }
                buildSensorMappingUI();
            }
        }

        // === Sensor Logic (kept and enhanced) ===
        let currentSensors = {};
        // Unwrap state for yaw (alpha). The browser delivers alpha as a
        // compass bearing 0..360 that wraps at 0/360. When the user
        // rotates past 180 -> -180 the raw value JUMPS (179 -> -179),
        // which makes the spatialization feel glitchy. We track the
        // cumulative angle (no wrap) and the most recent raw alpha so
        // unwrapYaw() can subtract the wrap correctly.
        let yawUnwrapped = 0;
        let yawLastAlpha = null;
        // Center / "calibration" offsets. When LIVE is pressed we
        // capture the current pose as the new zero, so the user
        // starts the session in whatever position feels natural to
        // them. Updates to these are applied to every subsequent
        // deviceorientation event in the listener.
        let centerOffset = { yaw: 0, pitch: 0, roll: 0 };
        let centerCalibrated = false;  // true after the first reading post-LIVE
        let liveSensorsActive = false;
        let sensorInfluence = 0.65;
        let lastSensorSend = 0;
        let orientationCanvasCtx = null;
        let sensorVizInterval = null;  // single shared interval, cleared on STOP/leave

        function updateSensorInfluence(val) {
            sensorInfluence = parseFloat(val);
            const el = document.getElementById('influence-val');
            if (el) el.textContent = parseFloat(val).toFixed(2);
        }

        function requestSensorPermissions() {
            const statusEl = document.getElementById('sensor-status');
            if (statusEl) statusEl.innerHTML = '<i class="fa-solid fa-circle text-amber-400 text-[8px]"></i> <span>Requesting...</span>';
            
            let promises = [];
            if (typeof DeviceOrientationEvent !== 'undefined' && typeof DeviceOrientationEvent.requestPermission === 'function') {
                promises.push(DeviceOrientationEvent.requestPermission());
            }
            if (typeof DeviceMotionEvent !== 'undefined' && typeof DeviceMotionEvent.requestPermission === 'function') {
                promises.push(DeviceMotionEvent.requestPermission());
            }
            
            Promise.all(promises).then(() => {
                if (statusEl) statusEl.innerHTML = '<i class="fa-solid fa-circle text-emerald-400 text-[8px]"></i> <span>Permissions OK</span>';
                startSensorListeners();
            }).catch(err => {
                if (statusEl) statusEl.innerHTML = '<i class="fa-solid fa-circle text-red-400 text-[8px]"></i> <span>Permission denied</span>';
            });
        }

        // Unwrap a compass bearing sequence (0..360) into a continuous
        // accumulating angle with no wrap. Each call integrates one new
        // sample; on the first call we just seed with the raw value.
        // We expose the helper as window.__unwrapYaw for the debug panel.
        function unwrapYaw(rawAlpha) {
            if (rawAlpha == null || isNaN(rawAlpha)) return yawUnwrapped;
            if (yawLastAlpha === null) {
                yawLastAlpha = rawAlpha;
                yawUnwrapped = rawAlpha;
                return yawUnwrapped;
            }
            let delta = rawAlpha - yawLastAlpha;
            // If the delta is more than 180 in absolute value, the sensor
            // crossed the 0/360 wrap point; correct by adding/subtracting 360.
            if (delta > 180)  delta -= 360;
            if (delta < -180) delta += 360;
            yawUnwrapped += delta;
            yawLastAlpha = rawAlpha;
            return yawUnwrapped;
        }
        window.__unwrapYaw = unwrapYaw;

        // Same idea for pitch (beta) — flips phone face-down makes beta
        // jump 180 → -180. Unwrap to a continuous accumulating angle.
        let pitchUnwrapped = 0;
        let pitchLastBeta = null;
        function unwrapPitch(rawBeta) {
            if (rawBeta == null || isNaN(rawBeta)) return pitchUnwrapped;
            if (pitchLastBeta === null) {
                pitchLastBeta = rawBeta;
                pitchUnwrapped = rawBeta;
                return pitchUnwrapped;
            }
            let delta = rawBeta - pitchLastBeta;
            if (delta > 180)  delta -= 360;
            if (delta < -180) delta += 360;
            pitchUnwrapped += delta;
            pitchLastBeta = rawBeta;
            return pitchUnwrapped;
        }
        window.__unwrapPitch = unwrapPitch;

        // And roll (gamma). Less common to wrap, but the same logic
        // applies if the user holds the phone at extreme angles.
        let rollUnwrapped = 0;
        let rollLastGamma = null;
        function unwrapRoll(rawGamma) {
            if (rawGamma == null || isNaN(rawGamma)) return rollUnwrapped;
            if (rollLastGamma === null) {
                rollLastGamma = rawGamma;
                rollUnwrapped = rawGamma;
                return rollUnwrapped;
            }
            let delta = rawGamma - rollLastGamma;
            if (delta > 180)  delta -= 360;
            if (delta < -180) delta += 360;
            rollUnwrapped += delta;
            rollLastGamma = rawGamma;
            return rollUnwrapped;
        }
        window.__unwrapRoll = unwrapRoll;

        function startSensorListeners() {
            window.addEventListener('deviceorientation', (event) => {
                const rawAlpha = event.alpha || 0;
                const rawBeta = event.beta || 0;
                const rawGamma = event.gamma || 0;
                // Store BOTH raw and offset-applied values:
                //  - raw (yawRaw etc) so the debug panel can show the wrap
                //  - centered values (yaw/pitch/roll) for the spatial
                //    mapping so the user can pick any "neutral" pose.
                // The unwrap* helpers make the centered value monotonic
                // even when the user rotates past the 180/-180 boundary.
                const unwrappedYaw   = unwrapYaw(rawAlpha);
                const unwrappedPitch = unwrapPitch(rawBeta);
                const unwrappedRoll  = unwrapRoll(rawGamma);
                currentSensors.yaw   = unwrappedYaw   - centerOffset.yaw;
                currentSensors.yawRaw = rawAlpha;
                currentSensors.pitch = unwrappedPitch - centerOffset.pitch;
                currentSensors.pitchRaw = rawBeta;
                currentSensors.roll  = unwrappedRoll  - centerOffset.roll;
                currentSensors.rollRaw = rawGamma;
                updateSensorDisplay();
                drawOrientationCanvas();
                if (liveSensorsActive) throttledSensorSend();
            }, true);

            window.addEventListener('devicemotion', (event) => {
                const acc = event.acceleration || event.accelerationIncludingGravity || {};
                const ax = acc.x || 0, ay = acc.y || 0, az = acc.z || 0;
                currentSensors.accel = Math.sqrt(ax*ax + ay*ay + az*az);
                
                const rot = event.rotationRate || {};
                const rx = rot.alpha || 0, ry = rot.beta || 0, rz = rot.gamma || 0;
                currentSensors.rotrate = Math.sqrt(rx*rx + ry*ry + rz*rz);
                
                updateSensorDisplay();
                if (liveSensorsActive) throttledSensorSend();
            }, true);
            
            const status = document.getElementById('sensor-status');
            if (status) status.innerHTML = '<i class="fa-solid fa-circle text-emerald-400 text-[8px]"></i> <span>Sensors active</span>';
        }

        function updateSensorDisplay() {
            // Update the sensor cards (populated by buildSensorCards)
            const cards = document.getElementById('sensor-cards');
            if (!cards) return;

            const sensors = [
                {key: 'yaw', label: 'YAW', unit: '°', color: '#f59e0b'},
                {key: 'pitch', label: 'PITCH', unit: '°', color: '#10b981'},
                {key: 'roll', label: 'ROLL', unit: '°', color: '#8b5cf6'},
                {key: 'accel', label: 'ACCEL', unit: 'm/s²', color: '#ef4444'}
            ];

            sensors.forEach(s => {
                const valEl = document.getElementById('sensor-val-' + s.key);
                const barEl = document.getElementById('sensor-bar-' + s.key);
                if (valEl) {
                    let v = currentSensors[s.key] || 0;
                    // Yaw is already unwrapped (no wrap at 180/-180). Show
                    // the actual continuous angle, mod 720 so the display
                    // stays readable after many rotations.
                    if (s.key === 'yaw') {
                        const shown = ((v % 720) + 720) % 720 - 360;
                        valEl.textContent = (v >= 0 ? '+' : '') + v.toFixed(0) + '° (' + shown.toFixed(0) + '°)';
                    } else {
                        valEl.textContent = v.toFixed(1) + s.unit;
                    }
                }
                if (barEl) {
                    let pct = 50;
                    let v = currentSensors[s.key] || 0;
                    if (s.key === 'yaw') {
                        // Map -360..360 to 0..100%, so the bar oscillates as
                        // the user rotates and visibly resets when they
                        // spin through 0 (vs. the old hard jump at 180).
                        pct = Math.min(100, Math.max(0, (v + 360) / 720 * 100));
                    }
                    else if (s.key === 'pitch') pct = Math.min(100, Math.max(0, (v + 90) / 180 * 100));
                    else if (s.key === 'roll') pct = Math.min(100, Math.max(0, (v + 90) / 180 * 100));
                    else if (s.key === 'accel') pct = Math.min(100, v * 15);
                    barEl.style.width = pct + '%';
                }
            });
        }

        function drawOrientationCanvas() {
            const canvas = document.getElementById('orientation-canvas');
            if (!canvas || !orientationCanvasCtx) return;
            const ctx = orientationCanvasCtx;
            const w = canvas.width;
            const h = canvas.height;
            
            ctx.clearRect(0, 0, w, h);
            
            const yaw = currentSensors.yaw || 0;
            const pitch = currentSensors.pitch || 0;
            const roll = currentSensors.roll || 0;

            // Background circle
            ctx.strokeStyle = '#1f2937';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(w/2, h/2 + 10, 52, 0, Math.PI * 2);
            ctx.stroke();

            // Horizon line (pitch influence). Clamp pitch to the canvas
            // bounds so unwrapped large values don't push it off-screen;
            // the underlying currentSensors.pitch still flows unbounded
            // to the spatial mapping.
            ctx.strokeStyle = '#475569';
            ctx.lineWidth = 1.5;
            const pitchForCanvas = Math.max(-90, Math.min(90, pitch));
            const horizonY = h/2 + 10 + (pitchForCanvas * 0.35);
            ctx.beginPath();
            ctx.moveTo(w/2 - 55, horizonY);
            ctx.lineTo(w/2 + 55, horizonY);
            ctx.stroke();

            // Yaw arrow — the canvas only shows the cardinal direction,
            // so we use the unwrapped yaw mod 360 to keep the arrow at
            // the correct bearing without spin-jumping.
            ctx.save();
            ctx.translate(w/2, h/2 + 10);
            const yawForArrow = ((yaw % 360) + 360) % 360;
            ctx.rotate((yawForArrow - 180) * Math.PI / 180);
            
            ctx.strokeStyle = '#f59e0b';
            ctx.lineWidth = 3;
            ctx.beginPath();
            ctx.moveTo(0, -28);
            ctx.lineTo(0, 28);
            ctx.stroke();
            
            // Arrow head
            ctx.fillStyle = '#f59e0b';
            ctx.beginPath();
            ctx.moveTo(0, -28);
            ctx.lineTo(-8, -18);
            ctx.lineTo(8, -18);
            ctx.fill();
            ctx.restore();
            
            // Roll indicator
            ctx.strokeStyle = '#8b5cf6';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(w/2 + 70, h/2 + 10, 18, 0, Math.PI * 2);
            ctx.stroke();
            
            ctx.fillStyle = '#8b5cf6';
            const rollRad = (roll * 0.01745);
            ctx.beginPath();
            ctx.arc(w/2 + 70 + Math.cos(rollRad) * 18, h/2 + 10 + Math.sin(rollRad) * 18, 4, 0, Math.PI * 2);
            ctx.fill();
            
            // Label
            const label = document.getElementById('orientation-label');
            if (label) {
                // Show unwrapped yaw as the canonical "how much have you
                // turned" reading, plus the cardinal bearing mod 360 so
                // the user can also see which compass direction they're
                // facing right now.
                const yawShown = ((yaw % 360) + 360) % 360;
                label.textContent = `Y:${yaw.toFixed(0)}° (→${yawShown.toFixed(0)}°) P:${pitch.toFixed(0)}° R:${roll.toFixed(0)}°`;
            }
        }

        function parseBands(bandsSpec) {
            if (!bandsSpec) return [];
            if (typeof bandsSpec === 'string') {
                if (bandsSpec === 'all') return Array.from({length:13}, (_,i)=>i+1);
                if (bandsSpec === 'low') return [1,2,3,4,5,6];
                if (bandsSpec === 'high') return [7,8,9,10,11,12,13];
                if (bandsSpec.includes('-')) {
                    const [s,e] = bandsSpec.split('-').map(Number);
                    return Array.from({length: e-s+1}, (_,i)=>s+i);
                }
                return bandsSpec.split(',').map(s => parseInt(s.trim())).filter(Boolean);
            }
            return Array.isArray(bandsSpec) ? bandsSpec : [];
        }

        function throttledSensorSend() {
            const now = Date.now();
            if (now - lastSensorSend < 55) return;
            lastSensorSend = now;
            computeAndSendSensorUpdates();
        }

        function computeAndSendSensorUpdates() {
            if (!liveSensorsActive || sensorInfluence <= 0) return;
            const mappings = getCurrentSensorMappings();
            const influence = sensorInfluence;

            // Build a single batch of updates so we send ONE HTTP request per
            // tick instead of N (one per band). This keeps the browser's
            // connection pool happy and the UI feels fluid.
            const updates = [];
            Object.entries(mappings).forEach(([sensorKey, map]) => {
                if (!map.enabled) return;

                let sensorVal = 0;
                if (sensorKey === 'yaw') {
                    // Already unwrapped by the listener — no % 360 here.
                    // Scale defaults to 1.0 → mod(-inf, +inf) range. UI
                    // mapping on the bands controls how fast az sweeps.
                    sensorVal = currentSensors.yaw || 0;
                }
                else if (sensorKey === 'pitch') sensorVal = currentSensors.pitch || 0;
                else if (sensorKey === 'roll') sensorVal = currentSensors.roll || 0;
                else if (sensorKey === 'accel') sensorVal = Math.max(0, (currentSensors.accel || 0) - 1) * 0.5;
                else if (sensorKey === 'rotrate') sensorVal = currentSensors.rotrate || 0;

                const targetParam = map.param;
                const bands = parseBands(map.bands);
                const scale = (map.scale || 1) * influence;
                const offset = map.offset || 0;

                let computed = sensorVal * scale + offset;

                if (targetParam === 'az') computed = Math.max(-180, Math.min(180, computed));
                if (targetParam === 'dist') computed = Math.max(0.5, Math.min(10, computed));
                if (targetParam === 'gain') computed = Math.max(0, Math.min(3, computed));
                if (targetParam === 'q') computed = Math.max(0.1, Math.min(2, computed));

                const isGlobal = (targetParam === 'mix' || targetParam === 'master');
                bands.forEach(bandIdx => {
                    const addr = isGlobal
                        ? `/beacon/${targetParam}`
                        : `/beacon/${targetParam}/${bandIdx}`;
                    updates.push({address: addr, value: computed});
                });
            });

            if (updates.length === 0) return;

            // Fire-and-forget: keepalive lets the browser send without holding
            // a connection open. No .then() / .catch() — sensor pipeline
            // shouldn't await ack on the critical path.
            try {
                fetch('/control/batch', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({updates: updates}),
                    keepalive: true
                });
            } catch (e) {
                // ignore — we don't care about the response on the audio path
            }
        }

        // === Beautiful new sensor mapping UI ===
        function buildSensorMappingUI() {
            const container = document.getElementById('sensor-mapping-rows');
            if (!container) return;
            
            const mappings = getCurrentSensorMappings();
            container.innerHTML = '';

            const sensors = ['yaw', 'pitch', 'roll', 'accel'];
            const paramOptions = ['az', 'dist', 'gain', 'q', 'mix', 'master'];
            const bandOptions = ['1-6', 'low', '7-12', 'high', 'all'];

            sensors.forEach(sensor => {
                const map = mappings[sensor] || {param: 'az', bands: '1-6', scale: 1, offset: 0, enabled: true};
                
                const row = document.createElement('div');
                row.className = 'sensor-card rounded-2xl p-3 flex flex-col gap-2';
                
                row.innerHTML = `
                    <div class="flex items-center justify-between">
                        <div class="font-semibold text-sm flex items-center gap-2" style="color: ${sensor === 'yaw' ? '#f59e0b' : sensor === 'pitch' ? '#10b981' : sensor === 'roll' ? '#8b5cf6' : '#ef4444'}">
                            <i class="fa-solid ${sensor === 'yaw' ? 'fa-compass' : sensor === 'pitch' ? 'fa-arrow-up' : sensor === 'roll' ? 'fa-sync' : 'fa-bolt'}"></i>
                            <span class="uppercase tracking-wider">${sensor}</span>
                        </div>
                        <label class="flex items-center gap-1 text-xs cursor-pointer">
                            <input type="checkbox" data-sensor="${sensor}" data-field="enabled" ${map.enabled ? 'checked' : ''} class="accent-cyan-400">
                            <span class="text-emerald-400 text-xs">ON</span>
                        </label>
                    </div>
                    
                    <div class="grid grid-cols-5 gap-2">
                        <div class="col-span-2">
                            <div class="text-[10px] text-slate-400 mb-0.5">PARAM</div>
                            <select data-sensor="${sensor}" data-field="param" class="bg-slate-950 border border-slate-700 text-xs rounded-xl px-2 py-1 w-full">
                                ${paramOptions.map(p => `<option value="${p}" ${map.param===p?'selected':''}>${p}</option>`).join('')}
                            </select>
                        </div>
                        <div class="col-span-2">
                            <div class="text-[10px] text-slate-400 mb-0.5">BANDS</div>
                            <select data-sensor="${sensor}" data-field="bands" class="bg-slate-950 border border-slate-700 text-xs rounded-xl px-2 py-1 w-full">
                                ${bandOptions.map(b => `<option value="${b}" ${map.bands===b?'selected':''}>${b}</option>`).join('')}
                            </select>
                        </div>
                        <div>
                            <div class="text-[10px] text-slate-400 mb-0.5">SCALE</div>
                            <input type="number" step="0.1" data-sensor="${sensor}" data-field="scale" value="${map.scale}" 
                                   class="bg-slate-950 border border-slate-700 text-xs rounded-xl px-2 py-1 w-full font-mono">
                        </div>
                    </div>
                    <div class="grid grid-cols-5 gap-2">
                        <div class="col-span-2">
                            <div class="text-[10px] text-slate-400 mb-0.5">OFFSET</div>
                            <input type="number" step="0.1" data-sensor="${sensor}" data-field="offset" value="${map.offset}" 
                                   class="bg-slate-950 border border-slate-700 text-xs rounded-xl px-2 py-1 w-full font-mono">
                        </div>
                    </div>
                `;
                
                container.appendChild(row);
                
                // listeners
                row.querySelectorAll('select, input').forEach(el => {
                    const handler = () => {
                        syncMappingFromUI();
                        updateDebugViz();
                    };
                    el.addEventListener('change', handler);
                    el.addEventListener('input', handler);
                });
            });
        }

        function syncMappingFromUI() {
            const container = document.getElementById('sensor-mapping-rows');
            if (!container) return;
            
            const newMappings = {};
            container.querySelectorAll('.sensor-card').forEach(card => {
                const sensor = card.querySelector('select[data-field="param"]').getAttribute('data-sensor');
                newMappings[sensor] = {
                    param: card.querySelector('select[data-field="param"]').value,
                    bands: card.querySelector('select[data-field="bands"]').value,
                    scale: parseFloat(card.querySelector('input[data-field="scale"]').value) || 1,
                    offset: parseFloat(card.querySelector('input[data-field="offset"]').value) || 0,
                    enabled: card.querySelector('input[data-field="enabled"]').checked
                };
            });
            
            const ta = document.getElementById('sensor-mapping-json');
            if (ta) ta.value = JSON.stringify(newMappings, null, 2);
        }

        function getCurrentSensorMappings() {
            const ta = document.getElementById('sensor-mapping-json');
            if (!ta || !ta.value.trim()) return getDefaultSensorMappings();
            try {
                return JSON.parse(ta.value);
            } catch (e) {
                return getDefaultSensorMappings();
            }
        }

        function getDefaultSensorMappings() {
            return {
                "yaw": { "param": "az", "bands": "1-6", "scale": 1.0, "offset": 0, "enabled": true },
                "pitch": { "param": "dist", "bands": "1-6", "scale": 0.025, "offset": 2.0, "enabled": true },
                "roll": { "param": "q", "bands": "7-12", "scale": 0.6, "offset": 0, "enabled": true },
                "accel": { "param": "gain", "bands": "1-6", "scale": 0.35, "offset": 0, "enabled": true }
            };
        }

        function updateDebugViz() {
            const drivingEl = document.getElementById('sensor-driving');
            if (!drivingEl || !liveSensorsActive) return;

            const mappings = getCurrentSensorMappings();
            const influence = sensorInfluence;
            let lines = [];

            Object.entries(mappings).forEach(([sensorKey, map]) => {
                if (!map.enabled) return;
                
                let sensorVal = currentSensors[sensorKey] || 0;
                if (sensorKey === 'yaw') sensorVal = ((sensorVal + 180) % 360) - 180;
                if (sensorKey === 'accel') sensorVal = Math.max(0, sensorVal - 1) * 0.5;

                const computed = sensorVal * (map.scale || 1) * influence + (map.offset || 0);
                const addr = `/beacon/${map.param}` + (map.param === 'mix' || map.param === 'master' ? '' : ' (' + map.bands + ')');
                
                lines.push(`${sensorKey.toUpperCase()} → ${map.param} ${map.bands}: ${computed.toFixed(2)}`);
            });

            drivingEl.textContent = lines.length ? lines.join('\\n') : '(no active mappings)';
        }

        function buildSensorCards() {
            const container = document.getElementById('sensor-cards');
            if (!container) return;
            
            const sensors = [
                {key:'yaw', label:'YAW', unit:'°', color:'#f59e0b', icon:'fa-compass'},
                {key:'pitch', label:'PITCH', unit:'°', color:'#10b981', icon:'fa-arrow-up'},
                {key:'roll', label:'ROLL', unit:'°', color:'#8b5cf6', icon:'fa-sync-alt'},
                {key:'accel', label:'ACCEL', unit:'', color:'#ef4444', icon:'fa-bolt'}
            ];
            
            container.innerHTML = '';
            
            sensors.forEach(s => {
                const div = document.createElement('div');
                div.className = `sensor-card rounded-2xl p-3 border border-slate-700`;
                div.innerHTML = `
                    <div class="flex justify-between items-start">
                        <div>
                            <div class="flex items-center gap-1.5">
                                <i class="fa-solid ${s.icon}" style="color:${s.color}"></i>
                                <span class="text-xs font-bold tracking-widest" style="color:${s.color}">${s.label}</span>
                            </div>
                            <div id="sensor-val-${s.key}" class="big-value font-mono mt-0.5" style="color:${s.color}">—</div>
                        </div>
                        <div class="text-right">
                            <div class="w-14 h-1.5 bg-slate-800 rounded mt-1.5 overflow-hidden">
                                <div id="sensor-bar-${s.key}" class="h-1.5 transition-all" style="width:50%; background:${s.color}"></div>
                            </div>
                        </div>
                    </div>
                `;
                container.appendChild(div);
            });
        }

        function toggleLiveSensorsUI() {
            liveSensorsActive = !liveSensorsActive;
            const btn = document.getElementById('live-btn');
            const text = document.getElementById('live-text');

            if (liveSensorsActive) {
                btn.classList.remove('bg-emerald-500/10', 'border-emerald-500/30', 'text-emerald-400');
                btn.classList.add('bg-emerald-500', 'border-emerald-500', 'text-white');
                text.textContent = 'STOP';

                const status = document.getElementById('sensor-status');
                if (status) status.innerHTML = '<i class="fa-solid fa-circle text-emerald-400 text-[8px]"></i> <span>LIVE — calibrating center…</span>';

                if (!currentSensors.yaw && !currentSensors.pitch) startSensorListeners();

                // Calibrate the center from the next deviceorientation
                // event. We schedule a one-shot capture so we use a real
                // sensor reading (not zeros from the cold start) as the
                // user's "neutral" pose.
                centerCalibrated = false;
                const onFirstEvent = (ev) => {
                    if (centerCalibrated) return;
                    const a = (ev.alpha != null) ? ev.alpha : 0;
                    const b = (ev.beta  != null) ? ev.beta  : 0;
                    const g = (ev.gamma != null) ? ev.gamma : 0;
                    // Reset unwrap state so the offset is applied against
                    // a clean baseline.
                    yawUnwrapped = a; yawLastAlpha = a;
                    pitchUnwrapped = b; pitchLastBeta = b;
                    rollUnwrapped = g; rollLastGamma = g;
                    centerOffset = { yaw: a, pitch: b, roll: g };
                    centerCalibrated = true;
                    if (status) status.innerHTML = '<i class="fa-solid fa-circle text-emerald-400 text-[8px]"></i> <span>LIVE — centered. Move freely.</span>';
                    window.removeEventListener('deviceorientation', onFirstEvent, true);
                };
                window.addEventListener('deviceorientation', onFirstEvent, true);

                // Viz loop: single shared interval, no leak on toggle
                if (sensorVizInterval) clearInterval(sensorVizInterval);
                sensorVizInterval = setInterval(() => {
                    if (!liveSensorsActive) return;
                    updateDebugViz();
                    drawOrientationCanvas();
                }, 160);
            } else {
                btn.classList.add('bg-emerald-500/10', 'border-emerald-500/30', 'text-emerald-400');
                btn.classList.remove('bg-emerald-500', 'border-emerald-500', 'text-white');
                text.textContent = 'LIVE';

                // Frenar limpio: parar el loop de viz, soltar el listener de calibración,
                // y congelar el envío (liveSensorsActive ya está en false → no se mandan más OSC).
                if (sensorVizInterval) { clearInterval(sensorVizInterval); sensorVizInterval = null; }
                centerCalibrated = false;
                const drv = document.getElementById('sensor-driving');
                if (drv) drv.textContent = '(LIVE detenido)';
                const status = document.getElementById('sensor-status');
                if (status) status.innerHTML = '<i class="fa-solid fa-circle text-slate-400 text-[8px]"></i> <span>Live detenido</span>';
            }
        }

        // Manual "set center to current pose" — usable mid-session if the
        // user wants to redefine "neutral" without stopping the live.
        function recenterSensors() {
            const a = currentSensors.yawRaw != null ? currentSensors.yawRaw : (currentSensors.yaw || 0);
            const b = currentSensors.pitchRaw != null ? currentSensors.pitchRaw : (currentSensors.pitch || 0);
            const g = currentSensors.rollRaw != null ? currentSensors.rollRaw : (currentSensors.roll || 0);
            // Reset unwrap accumulators so subsequent values are relative
            // to this pose and stay monotonic.
            yawUnwrapped = a; yawLastAlpha = a;
            pitchUnwrapped = b; pitchLastBeta = b;
            rollUnwrapped = g; rollLastGamma = g;
            centerOffset = { yaw: a, pitch: b, roll: g };
            centerCalibrated = true;
            const status = document.getElementById('sensor-status');
            if (status) status.innerHTML = '<i class="fa-solid fa-circle text-emerald-400 text-[8px]"></i> <span>Recentered.</span>';
        }

        function getSensorMappingJSONEl() {
            let ta = document.getElementById('sensor-mapping-json');
            if (!ta) {
                ta = document.createElement('textarea');
                ta.id = 'sensor-mapping-json';
                ta.style.display = 'none';
                document.body.appendChild(ta);
            }
            return ta;
        }

        function initSensorUI() {
            // Create hidden JSON textarea for compatibility
            const ta = getSensorMappingJSONEl();
            ta.value = JSON.stringify(getDefaultSensorMappings(), null, 2);
            
            // Build beautiful UI components
            buildSensorCards();
            buildSensorMappingUI();
            
            // Orientation canvas
            const canvas = document.getElementById('orientation-canvas');
            if (canvas) {
                orientationCanvasCtx = canvas.getContext('2d');
                // initial draw
                setTimeout(drawOrientationCanvas, 300);
            }
            
            // Influence init
            const inf = document.getElementById('sensor-influence');
            if (inf) {
                inf.value = sensorInfluence;
                const valEl = document.getElementById('influence-val');
                if (valEl) valEl.textContent = sensorInfluence.toFixed(2);
            }

            // Viz loop is created on first LIVE press (toggleLiveSensorsUI)
            // — not here, to avoid running before the user opts in.
        }

        function resetSensorMappingToDefault() {
            const ta = getSensorMappingJSONEl();
            ta.value = JSON.stringify(getDefaultSensorMappings(), null, 2);
        }

        function saveSensorConfigToPreset() {
            const nameInput = document.getElementById('save-name');
            if (nameInput && !nameInput.value.trim()) {
                nameInput.value = 'sensor-' + Date.now().toString(36);
            }
            saveConfig();
        }

        function exportSensorConfig() {
            const ta = getSensorMappingJSONEl();
            const data = ta.value || JSON.stringify(getCurrentSensorMappings(), null, 2);
            const blob = new Blob([data], {type: 'application/json'});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'beacon-sensor-mapping.json';
            a.click();
            URL.revokeObjectURL(url);
        }

        // Load/Save config (kept intact)
        function loadConfig() {
            const sel = document.getElementById('load-select-large') || document.getElementById('load-select');
            const name = sel ? sel.value : '';
            if (!name) { 
                const status = document.getElementById('config-status');
                if (status) status.textContent = 'Select a preset';
                return; 
            }
            fetch('/load_config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name: name})
            }).then(r => r.json()).then(data => {
                if (data.ok && data.state) {
                    applyState(data.state);
                    const status = document.getElementById('config-status');
                    if (status) status.textContent = 'Loaded: ' + name;
                } else {
                    const status = document.getElementById('config-status');
                    if (status) status.textContent = 'Error loading';
                }
            }).catch(err => {
                const status = document.getElementById('config-status');
                if (status) status.textContent = 'Load error';
            });
        }

        function loadConfigList() {
            fetch('/list_configs').then(r => r.json()).then(data => {
                const sel = document.getElementById('load-select');
                if (!sel) return;   // el dropdown visible es load-select-large (lo puebla renderPresetCards)
                sel.innerHTML = '<option value="">Load preset...</option>';
                (data.configs || []).forEach(c => {
                    const opt = document.createElement('option');
                    opt.value = c;
                    opt.textContent = c;
                    sel.appendChild(opt);
                });
            });
        }

        function saveConfig() {
            const name = document.getElementById('save-name').value.trim() || 'untitled-' + Date.now();
            const state = gatherState();
            
            fetch('/save_config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name: name, state: state})
            }).then(r => r.json()).then(data => {
                const status = document.getElementById('config-status');
                if (status) status.textContent = data.ok ? 'Saved: ' + name : 'Save failed';
                loadConfigList();
                setTimeout(() => { if (status) status.textContent = 'Presets ready'; }, 1800);
            });
        }

        // Initialize everything
        function initializeUI() {
            initTailwind();

            // Initial values for mix/master
            const mix = document.getElementById('mix');
            const master = document.getElementById('master');
            if (mix) show(mix, 'vmix');
            if (master) show(master, 'vmaster');

            // Wire up tab buttons
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    const target = btn.getAttribute('data-tab-target');
                    switchTab(target);
                });
            });

            // Boot sensor stuff
            initSensorUI();
            initSpatial();
            uiTick();
            loadConfigList();
            renderPresetCards();

            // Default influence
            updateSensorInfluence(sensorInfluence);

            // Restore last tab (or default to manual)
            const qp = new URLSearchParams(location.search).get('tab');
            const last = qp || localStorage.getItem('beacon.activeTab') || 'spatial';
            switchTab(last);

            // First paint of sensor debug panel
            updateSensorDebugPanel();

            // Keyboard hint
            console.log('%c[Beacon] Excellent UI loaded. Sensors ready for phone.', 'color:#64748b');
        }

        function switchTab(name) {
            // Show/hide panels
            document.querySelectorAll('.tab-panel').forEach(p => {
                p.hidden = p.getAttribute('data-tab') !== name;
            });
            // Style active button
            document.querySelectorAll('.tab-btn').forEach(b => {
                const active = b.getAttribute('data-tab-target') === name;
                b.classList.toggle('border-cyan-500/40', active);
                b.classList.toggle('bg-cyan-500/10', active);
                b.classList.toggle('text-cyan-300', active);
                b.classList.toggle('border-slate-700', !active);
                b.classList.toggle('bg-slate-900', !active);
                b.classList.toggle('text-slate-400', !active);
            });
            localStorage.setItem('beacon.activeTab', name);
            // Campo espacial: arrancar/parar el loop de dibujo
            spatialActive = (name === 'spatial');
            if (spatialActive) { spSetupCanvas(); requestAnimationFrame(spatialTick); }
        }

        function renderPresetCards() {
            fetch('/list_configs').then(r => r.json()).then(data => {
                const configs = data.configs || [];
                const big = document.getElementById('load-select-large');
                const small = document.getElementById('load-select');
                const cards = document.getElementById('preset-cards');
                const count = document.getElementById('preset-count');
                if (count) count.textContent = configs.length + ' files';

                if (big) {
                    big.innerHTML = '<option value="">— pick a preset —</option>';
                    configs.forEach(c => {
                        const opt = document.createElement('option');
                        opt.value = c; opt.textContent = c;
                        big.appendChild(opt);
                    });
                }
                if (small) {
                    // The original top-bar small select (kept for back-compat)
                    small.innerHTML = '<option value="">Load preset...</option>';
                    configs.forEach(c => {
                        const opt = document.createElement('option');
                        opt.value = c; opt.textContent = c;
                        small.appendChild(opt);
                    });
                }
                if (cards) {
                    cards.innerHTML = '';
                    configs.forEach(c => {
                        const card = document.createElement('button');
                        card.className = 'text-left rounded-2xl border border-slate-800 bg-slate-900 hover:bg-slate-800 hover:border-cyan-500/40 transition-colors p-3';
                        card.innerHTML = '<div class="flex items-center gap-2 mb-1">' +
                            '<i class="fa-solid fa-file-audio text-cyan-400 text-sm"></i>' +
                            '<span class="font-mono text-sm text-slate-200">' + c + '</span>' +
                            '</div>' +
                            '<div class="text-[10px] text-slate-500">click to load</div>';
                        card.onclick = () => {
                            const b=document.getElementById('load-select-large'); if(b) b.value=c;
                            loadConfig();
                        };
                        cards.appendChild(card);
                    });
                }
            });
        }

        // === Sensor Debug Panel (no DevTools required) ===
        // Counter of received events — updated by listeners, read by debug panel.
        let sensorEventCounts = {deviceorientation: 0, devicemotion: 0, lastOrientTs: 0, lastMotionTs: 0};
        let sensorDebugErrors = [];
        let sensorFetchCount = 0;
        let sensorLastFetchTs = 0;
        let sensorFirstError = null;
        let sensorDebugLastRender = 0;

        function updateSensorDebugPanel() {
            // Throttle: skip if last render was <100ms ago (prevents excessive work
            // when called from the setInterval AND from event listeners).
            const el = document.getElementById('sensor-debug-panel');
            if (!el) return;
            const now = Date.now();
            if (now - sensorDebugLastRender < 100) return;
            sensorDebugLastRender = now;

            // Detect support (defensive: every property read wrapped in try)
            let hasOrient = false, hasMotion = false, needsPerm = false;
            let isSecure = false, isHttps = false, isLocal = false, uaStr = 'unknown';
            try {
                hasOrient = typeof DeviceOrientationEvent !== 'undefined';
                hasMotion = typeof DeviceMotionEvent !== 'undefined';
                needsPerm = !!(hasOrient && typeof DeviceOrientationEvent.requestPermission === 'function');
                isSecure = !!window.isSecureContext;
                isHttps = location.protocol === 'https:';
                isLocal = location.hostname === 'localhost' || location.hostname === '127.0.0.1';
                const m = (navigator.userAgent || '').match(/(iPhone|iPad|iPod|Android|Macintosh|Linux|Windows)/i);
                uaStr = m ? m[0] : 'unknown';
            } catch (e) {
                sensorFirstError = sensorFirstError || ('detect: ' + e.message);
            }

            const orientAge = sensorEventCounts.lastOrientTs ? Math.round((now - sensorEventCounts.lastOrientTs) / 100) / 10 : null;
            const motionAge = sensorEventCounts.lastMotionTs ? Math.round((now - sensorEventCounts.lastMotionTs) / 100) / 10 : null;
            const fetchAge = sensorLastFetchTs ? Math.round((now - sensorLastFetchTs) / 100) / 10 : null;

            // Build with textContent (no HTML injection / no crash on null)
            const lines = [
                'browser:        ' + uaStr + ' / ' + location.protocol + '//' + location.hostname,
                'secureContext:  ' + isSecure,
                'HTTPS/local?    ' + (isHttps || isLocal ? 'YES ✓' : 'NO ✗ (sensors may be blocked on LAN http)'),
                'DeviceOrient:   ' + (hasOrient ? 'YES' : 'NO'),
                'DeviceMotion:   ' + (hasMotion ? 'YES' : 'NO'),
                'iOS perm API:   ' + (needsPerm ? 'YES (tap Permissions!)' : 'no'),
                'LIVE state:     ' + (liveSensorsActive ? 'ON' : 'OFF'),
                'orient events:  ' + sensorEventCounts.deviceorientation + (orientAge !== null ? '  (last: ' + orientAge + 's ago)' : '  (never)'),
                'motion events:  ' + sensorEventCounts.devicemotion + (motionAge !== null ? '  (last: ' + motionAge + 's ago)' : '  (never)'),
                'fetch /control: ' + sensorFetchCount + (fetchAge !== null ? '  (last: ' + fetchAge + 's ago)' : '  (never)'),
                'yaw raw→unwrap: ' + (currentSensors.yawRaw != null ? currentSensors.yawRaw.toFixed(0) + '° → ' + (currentSensors.yaw || 0).toFixed(0) + '°' : 'n/a'),
                'pitch raw→unwrap: ' + (currentSensors.pitchRaw != null ? currentSensors.pitchRaw.toFixed(0) + '° → ' + (currentSensors.pitch || 0).toFixed(0) + '°' : 'n/a'),
                'center offset:   ' + (centerCalibrated ? 'yaw=' + centerOffset.yaw.toFixed(0) + '° pitch=' + centerOffset.pitch.toFixed(0) + '° roll=' + centerOffset.roll.toFixed(0) + '°' : 'not calibrated'),
                'last error:     ' + (sensorFirstError || 'none'),
            ];

            // textContent assignment is safe (no HTML parsing, no XSS, no null crash)
            // Use String.fromCharCode(10) as a real newline (the JS escape
            // sequence breaks when this script is inside a Python
            // triple-quoted string and a literal newline creeps in).
            const NL = String.fromCharCode(10);
            try {
                el.textContent = lines.join(NL);
            } catch (e) {
                // Last-ditch fallback
            }

            // Add warnings as separate <div>s (only when applicable)
            try {
                let warnings = '';
                if (!isHttps && !isLocal) {
                    warnings += '<div class="text-amber-400 mt-1.5">⚠ sensors are BLOCKED on http://&lt;LAN-IP&gt;. Use https:// or tunnel via cloudflared/ngrok.</div>';
                }
                if (needsPerm && sensorEventCounts.deviceorientation === 0 && liveSensorsActive) {
                    warnings += '<div class="text-amber-400 mt-1.5">⚠ iOS: tap the Permissions button (top bar) — sensors need a one-time gesture unlock.</div>';
                }
                if (hasOrient && liveSensorsActive && sensorEventCounts.deviceorientation === 0 && (orientAge === null || orientAge > 2)) {
                    warnings += '<div class="text-amber-400 mt-1.5">⚠ LIVE is ON but no orientation events have arrived in 2s+.</div>';
                }
                // Append warnings as a sibling node we control
                let warnEl = document.getElementById('sensor-debug-warnings');
                if (!warnEl && warnings) {
                    warnEl = document.createElement('div');
                    warnEl.id = 'sensor-debug-warnings';
                    el.parentNode?.insertBefore(warnEl, el.nextSibling);
                }
                if (warnEl) warnEl.innerHTML = warnings;
            } catch (e) {
                // ignore
            }
        }

        // Hook into listeners to count events.
        // We add our own listeners that ONLY count, so they coexist with
        // the real sensor listeners installed by startSensorListeners().
        window.addEventListener('deviceorientation', () => {
            sensorEventCounts.deviceorientation++;
            sensorEventCounts.lastOrientTs = Date.now();
        }, true);
        window.addEventListener('devicemotion', () => {
            sensorEventCounts.devicemotion++;
            sensorEventCounts.lastMotionTs = Date.now();
        }, true);

        // Hook fetch to count /control calls (defensive: check Function is OK)
        try {
            const __origFetch = window.fetch;
            if (__origFetch && !window.__beaconFetchHooked) {
                window.__beaconFetchHooked = true;
                window.fetch = function(url, opts) {
                    try {
                        const u = (typeof url === 'string') ? url : (url?.url || '');
                        if (u.includes('/control')) {
                            sensorFetchCount++;
                            sensorLastFetchTs = Date.now();
                        }
                    } catch (e) { /* ignore */ }
                    return __origFetch.apply(this, arguments);
                };
            }
        } catch (e) {
            sensorFirstError = sensorFirstError || ('fetch hook: ' + e.message);
        }

        // Capture errors globally
        try {
            window.addEventListener('error', e => {
                sensorFirstError = sensorFirstError || (e.message + ' @ ' + (e.filename || '') + ':' + (e.lineno || ''));
            });
            window.addEventListener('unhandledrejection', e => {
                sensorFirstError = sensorFirstError || 'promise: ' + String(e.reason).substring(0, 200);
            });
        } catch (e) { /* ignore */ }

        // Auto-refresh the debug panel every 500ms
        setInterval(updateSensorDebugPanel, 500);

        // Also update right after a sensor event fires (immediate feedback)
        const __updateAfterOrient = () => { sensorDebugLastRender = 0; updateSensorDebugPanel(); };
        window.addEventListener('deviceorientation', __updateAfterOrient, true);
        window.addEventListener('devicemotion', __updateAfterOrient, true);

        function loadConfigFromLargeSelect() {
            loadConfig();   // loadConfig ya lee load-select-large
        }

        window.onload = initializeUI;
    </script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML, bands=BANDS)

@app.route("/control", methods=["POST"])
def control():
    data = request.get_json()
    addr = data.get("address", "")
    raw = data.get("value", 0)
    # OSC value must be numeric; coerce strings to float when possible.
    # record/start|stop can carry a non-numeric label, so we forward a
    # numeric 1/0 to sclang and use the address itself to convey intent.
    try:
        val = float(raw)
    except (TypeError, ValueError):
        val = 1.0 if isinstance(raw, str) and raw else 0.0
    osc.send_message(addr, val)
    # Also forward to PD replica sclang (port 9001) if running
    try:
        osc_pd.send_message(addr, val)
    except Exception:
        pass  # PD replica not running — silently ignore
    return jsonify({"ok": True})

@app.route("/control/batch", methods=["POST"])
def control_batch():
    # Sensor pipeline sends all per-tick updates in one POST so the
    # browser's connection pool isn't exhausted at high event rates.
    data = request.get_json() or {}
    updates = data.get("updates") or []
    if not isinstance(updates, list):
        return jsonify({"ok": False, "error": "updates must be a list"}), 400
    sent = 0
    for u in updates:
        if not isinstance(u, dict):
            continue
        addr = u.get("address", "")
        raw = u.get("value", 0)
        try:
            val = float(raw)
        except (TypeError, ValueError):
            val = 1.0 if isinstance(raw, str) and raw else 0.0
        try:
            osc.send_message(addr, val)
            sent += 1
        except Exception:
            pass
        try:
            osc_pd.send_message(addr, val)
        except Exception:
            pass
    return jsonify({"ok": True, "sent": sent})

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

@app.route("/level")
def level():
    return jsonify({"level": _LATEST["level"]})

# ---- Salida seleccionable: re-rutea SuperCollider:out_1/2 al sink elegido vía pw-link ----
def _pwlink(*args, timeout=4):
    try:
        return subprocess.run(["pw-link", *args], capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None

def _playback_ports():
    r = _pwlink("-i")
    ports = []
    if r:
        for line in r.stdout.splitlines():
            line = line.strip()
            if ":" in line and "playback" in line.lower():
                ports.append(line)
    return ports

def _output_nodes():
    nodes = {}
    for p in _playback_ports():
        nodes.setdefault(p.rsplit(":", 1)[0], []).append(p)
    return nodes

def _out_label(node):
    n = node.lower()
    if "fosi" in n: return "Fosi Audio DS2"
    if "headphones" in n: return "Auriculares internos"
    if "hdmi3" in n: return "HDMI 3"
    if "hdmi2" in n: return "HDMI 2"
    if "hdmi1" in n: return "HDMI 1"
    if "midi" in n or "bridge" in n: return None  # excluir
    lbl = node.split(".")[-1].replace("__sink", "").replace("_", " ").strip()
    return lbl or node

def _current_output():
    # a qué nodo está conectado SuperCollider:out_1 (parse de `pw-link -l`)
    r = _pwlink("-l")
    if not r:
        return ""
    cur = None
    for raw in r.stdout.splitlines():
        if not raw.strip():
            continue
        if raw[:1].isspace():
            s = raw.strip()
            if cur == "SuperCollider:out_1" and "|->" in s:
                target = s.split("|->", 1)[1].strip()
                if ":" in target:
                    return target.rsplit(":", 1)[0]
        else:
            cur = raw.strip()
    return ""

@app.route("/list_outputs")
def list_outputs():
    outs = []
    for node, ports in _output_nodes().items():
        lbl = _out_label(node)
        if lbl and len(ports) >= 2:
            outs.append({"node": node, "label": lbl})
    outs.sort(key=lambda o: o["label"])
    return jsonify({"ok": True, "outputs": outs, "current": _current_output()})

@app.route("/output", methods=["POST"])
def set_output():
    node = ((request.get_json() or {}).get("node") or "").strip()
    ports = sorted(_output_nodes().get(node, []))
    if len(ports) < 2:
        return jsonify({"ok": False, "error": "sin puertos"}), 400
    # desconectar la salida de SuperCollider de todos los playbacks, luego conectar al elegido
    for src in ("SuperCollider:out_1", "SuperCollider:out_2"):
        for p in _playback_ports():
            _pwlink("-d", src, p)
    _pwlink("SuperCollider:out_1", ports[0])
    _pwlink("SuperCollider:out_2", ports[1])
    return jsonify({"ok": True, "node": node, "label": _out_label(node)})

# ---- Entrada seleccionable (modo "En vivo"): rutea una captura → SuperCollider:in_1 ----
def _capture_ports():
    r = _pwlink("-o")
    ports = []
    if r:
        for line in r.stdout.splitlines():
            line = line.strip()
            low = line.lower()
            if ":" not in line:
                continue
            if any(x in low for x in ("monitor", "supercollider", "midi", "v4l2")):
                continue
            if "capture" in low or "alsa_input" in low:
                ports.append(line)
    return ports

def _input_nodes():
    nodes = {}
    for p in _capture_ports():
        nodes.setdefault(p.rsplit(":", 1)[0], []).append(p)
    return nodes

def _in_label(node):
    n = node.lower()
    if "fosi" in n: return "Fosi (entrada)"
    if "zoom" in n or "r24" in n or "r16" in n: return "Zoom (placa)"
    if "mic1" in n: return "Mic interno 1"
    if "mic2" in n: return "Mic interno 2"
    lbl = node.split(".")[-1].replace("__source", "").replace("_", " ").strip()
    return lbl or node

def _current_input():
    r = _pwlink("-l")
    if not r:
        return ""
    cur = None
    for raw in r.stdout.splitlines():
        if not raw.strip():
            continue
        if raw[:1].isspace():
            s = raw.strip()
            if cur == "SuperCollider:in_1" and "|<-" in s:
                src = s.split("|<-", 1)[1].strip()
                if ":" in src:
                    return src.rsplit(":", 1)[0]
        else:
            cur = raw.strip()
    return ""

@app.route("/list_inputs")
def list_inputs():
    ins = []
    for node, ports in _input_nodes().items():
        lbl = _in_label(node)
        if lbl and ports:
            ins.append({"node": node, "label": lbl})
    ins.sort(key=lambda o: o["label"])
    return jsonify({"ok": True, "inputs": ins, "current": _current_input()})

@app.route("/input", methods=["POST"])
def set_input():
    node = ((request.get_json() or {}).get("node") or "").strip()
    ports = sorted(_input_nodes().get(node, []))
    if not ports:
        return jsonify({"ok": False, "error": "sin puertos"}), 400
    for p in _capture_ports():           # desconectar in_1 de toda captura
        _pwlink("-d", p, "SuperCollider:in_1")
    _pwlink(ports[0], "SuperCollider:in_1")   # captura elegida → entrada de SC (SoundIn.ar(0))
    return jsonify({"ok": True, "node": node, "label": _in_label(node)})

@app.route("/list_sources")
def list_sources():
    # WAVs disponibles como fuente (aporte BEACON-sound) + cuál reproduce el engine (BEACON_AUDIO)
    files = sorted(glob.glob(os.path.join(SOURCES_DIR, "*.wav")))
    sources = [{"name": os.path.basename(f), "path": f} for f in files]
    playing = os.path.basename(os.environ.get("BEACON_AUDIO", "")) or (sources[0]["name"] if sources else "")
    return jsonify({"ok": True, "dir": SOURCES_DIR, "sources": sources, "playing": playing})

@app.route("/source", methods=["POST"])
def source():
    # Cambia el WAV fuente en vivo: OSC /beacon/source/file <path> → beacon.scd
    data = request.get_json() or {}
    path = (data.get("path") or "").strip()
    if not path or not os.path.exists(path):
        return jsonify({"ok": False, "error": "bad path"}), 400
    osc.send_message("/beacon/source/file", path)
    return jsonify({"ok": True, "path": path})

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
    # threaded=True so concurrent sensor-batch POSTs don't serialize
    # behind each other on the Werkzeug dev server's main request loop.
    app.run(host="0.0.0.0", port=5050, debug=False, threaded=True)
