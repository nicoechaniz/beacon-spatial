#!/usr/bin/env python3
"""OSC bridge: Open Stage Control -> Pd via TCP/FUDI.

Run this alongside the Pd patch. It receives OSC from Open Stage Control
on UDP port 9000 and forwards text commands to Pd's [netreceive 8000 1].

OSC address format:
  /beacon/gain/1 <float>   ->  b1 gain <float>
  /beacon/az/1 <float>     ->  b1 az <float>
  /beacon/dist/1 <float>   ->  b1 dist <float>
  /beacon/wet <float>      ->  wet <float>
  /beacon/dry <float>      ->  dry <float>
  /beacon/master <float>   ->  master <float>
  /beacon/lfo/offset <float> -> lfo offset <float>

Usage:
  python3 bridge.py
"""

import socket
import sys
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer

PD_HOST = "localhost"
PD_PORT = 8000
OSC_PORT = 9000


def to_pd(addr: str, *args):
    """Convert OSC address to Pd FUDI message."""
    parts = addr.strip("/").split("/")
    if len(parts) < 2 or parts[0] != "beacon":
        return

    val = round(args[0], 4) if args else 0

    if len(parts) == 3 and parts[1] == "lfo":
        # /beacon/lfo/offset -> lfo offset <val>
        msg = f"lfo {parts[2]} {val};\n"
    elif len(parts) == 3:
        # /beacon/gain/1 -> b1 gain <val>
        param, idx = parts[1], parts[2]
        name = f"b{idx}"
        msg = f"{name} {param} {val};\n"
    elif len(parts) == 2:
        # /beacon/wet -> wet <val>
        msg = f"{parts[1]} {val};\n"
    else:
        return

    try:
        pd_sock.send(msg.encode())
    except Exception as e:
        print(f"send error: {e}")


def main():
    global pd_sock
    pd_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        pd_sock.connect((PD_HOST, PD_PORT))
        print(f"Connected to Pd on {PD_HOST}:{PD_PORT}")
    except ConnectionRefusedError:
        print(f"ERROR: Cannot connect to Pd at {PD_HOST}:{PD_PORT}")
        print("Make sure Pd is running with [netreceive 8000 1] loaded.")
        sys.exit(1)

    dispatcher = Dispatcher()
    dispatcher.map("/beacon/*", to_pd)

    server = BlockingOSCUDPServer(("0.0.0.0", OSC_PORT), dispatcher)
    print(f"OSC server listening on UDP port {OSC_PORT}")
    print("Open Stage Control should send to this port.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        pd_sock.close()
        server.shutdown()


if __name__ == "__main__":
    main()
