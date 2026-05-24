#!/usr/bin/env python3
"""Test the OSC bridge without running Pd."""

import socket
import threading
import time
from pythonosc.udp_client import SimpleUDPClient

# Mock Pd TCP server
received = []

def mock_pd_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("localhost", 8000))
    s.listen(1)
    print("Mock Pd listening on :8000")
    conn, addr = s.accept()
    print(f"Bridge connected from {addr}")
    while True:
        data = conn.recv(1024)
        if not data:
            break
        for line in data.decode().strip().split(";"):
            line = line.strip()
            if line:
                received.append(line)
                print(f"  Pd received: {line}")
    conn.close()

# Start mock Pd
pd_thread = threading.Thread(target=mock_pd_server, daemon=True)
pd_thread.start()
time.sleep(0.3)

# Start bridge
import subprocess
bridge = subprocess.Popen(
    ["python3", "bridge.py"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)
time.sleep(0.5)

# Send OSC messages
client = SimpleUDPClient("127.0.0.1", 9000)
print("\nSending OSC messages...")
client.send_message("/beacon/gain/1", 1.5)
client.send_message("/beacon/az/2", 90)
client.send_message("/beacon/dist/3", 5.0)
client.send_message("/beacon/wet", 0.7)
client.send_message("/beacon/dry", 0.4)
client.send_message("/beacon/master", 1.2)
client.send_message("/beacon/lfo/offset", 45)

time.sleep(0.5)

# Check results
print(f"\n=== Results ===")
print(f"Received {len(received)} messages:")
for r in received:
    print(f"  {r}")

expected = [
    "b1 gain 1.5",
    "b2 az 90",
    "b3 dist 5.0",
    "wet 0.7",
    "dry 0.4",
    "master 1.2",
    "lfo offset 45"
]

all_ok = True
for e in expected:
    found = any(e in r for r in received)
    status = "OK" if found else "MISSING"
    print(f"  [{status}] {e}")
    if not found:
        all_ok = False

bridge.terminate()
print(f"\nTest {'PASSED' if all_ok else 'FAILED'}")
