#!/usr/bin/env python3
"""Send test OSC messages to Pd on port 9001."""
from pythonosc.udp_client import SimpleUDPClient
import time

client = SimpleUDPClient("127.0.0.1", 9001)

print("Sending test OSC messages to 127.0.0.1:9001 every second...")
print("Press Ctrl+C to stop.")

try:
    while True:
        client.send_message("/beacon/gain/1", [1.5])
        print("Sent: /beacon/gain/1 1.5")
        time.sleep(1)
        client.send_message("/beacon/az/1", [90.0])
        print("Sent: /beacon/az/1 90.0")
        time.sleep(1)
except KeyboardInterrupt:
    print("\nStopped.")
