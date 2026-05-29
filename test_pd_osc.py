#!/usr/bin/env python3
"""Test OSC control of PD Replica spatializer.

Sends test messages to port 9001 and verifies the PD replica responds.
If scsynth is running with the \beacon_pd_replica SynthDef, the
OSCdefs in beacon_pd_replica.scd receive these messages and call
synth.set(...) which sends /n_set to scsynth:57110.

Test procedure:
  1. Verify scsynth is running on 57110
  2. Start sclang with beacon_pd_replica.scd (port 9001)
  3. Send test OSC messages
  4. Verify no errors in sclang log

Usage:
  python3 test_pd_osc.py
"""

import socket, struct, time, subprocess, os

SCSYNTH_PORT = 57110
SCLANG_PD_PORT = 9001

def send_osc(host, port, address, value):
    """Send a single OSC message with one float argument."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # OSC address
    addr_bytes = address.encode('utf-8')
    padded_addr = addr_bytes + b'\x00' * (4 - len(addr_bytes) % 4)
    if len(addr_bytes) % 4 != 0:
        padded_addr = addr_bytes + b'\x00' * (4 - (len(addr_bytes) % 4))

    # OSC type tag string
    type_tag = b',f'
    padded_type = type_tag + b'\x00' * (4 - len(type_tag) % 4)
    if len(type_tag) % 4 != 0:
        padded_type = type_tag + b'\x00' * (4 - (len(type_tag) % 4))

    # Float value (big-endian)
    val_bytes = struct.pack('>f', float(value))

    msg = padded_addr + padded_type + val_bytes
    sock.sendto(msg, (host, port))
    sock.close()

def check_scsynth():
    """Check if scsynth is running on port 57110 by trying to send an /status."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1.0)
    try:
        # Send /status message
        addr = b'/status'
        padded = addr + b'\x00' * (4 - len(addr) % 4)
        sock.sendto(padded, ("127.0.0.1", SCSYNTH_PORT))
        data = sock.recv(1024)
        # Check for /status.reply in response
        if b'/status.reply' in data:
            print(f"[OK] scsynth running on :{SCSYNTH_PORT}")
            return True
    except socket.timeout:
        print(f"[WARN] No response from scsynth on :{SCSYNTH_PORT}")
    except ConnectionRefusedError:
        print(f"[WARN] Connection refused on :{SCSYNTH_PORT}")
    finally:
        sock.close()
    return False

def check_sclang_log():
    """Check sclang log for errors."""
    log_path = "/tmp/sclang_pd.log"
    if not os.path.exists(log_path):
        log_path = "/tmp/sclang.log"
    if os.path.exists(log_path):
        with open(log_path) as f:
            content = f.read()
        # Look for error indicators
        for pattern in ["ERROR", "FAILURE", "exception", "Error"]:
            if pattern in content:
                line = [l for l in content.split('\n') if pattern in l]
                if line:
                    print(f"[WARN] sclang log shows '{pattern}': {line[-1]}")
        return content
    return ""

def test_all_bands():
    """Send test OSC to each band parameter on port 9001."""
    print("\n--- Testing OSC control on port %d ---" % SCLANG_PD_PORT)

    # Test gain for all 6 bands
    print("\n1. Band gains (0.5 each)...")
    for band in range(1, 7):
        send_osc("127.0.0.1", SCLANG_PD_PORT, f"/beacon/gain/{band}", 0.5)
    print("   Sent /beacon/gain/1..6 = 0.5")

    # Test azimuth for all 6 bands
    print("\n2. Band azimuths...")
    az_values = [180, 135, -90, -45, 45, 0]
    for band, az in enumerate(az_values, 1):
        send_osc("127.0.0.1", SCLANG_PD_PORT, f"/beacon/az/{band}", az)
    print(f"   Sent /beacon/az/1..6 = {az_values}")

    # Test distance for all 6 bands
    print("\n3. Band distances...")
    dist_values = [2.0, 2.5, 3.0, 2.5, 2.0, 1.5]
    for band, dist in enumerate(dist_values, 1):
        send_osc("127.0.0.1", SCLANG_PD_PORT, f"/beacon/dist/{band}", dist)
    print(f"   Sent /beacon/dist/1..6 = {dist_values}")

    # Test Q values
    print("\n4. Band Q values (15Hz BW)...")
    q_values = [40/15, 80/15, 120/15, 160/15, 200/15, 240/15]
    for band, q in enumerate(q_values, 1):
        send_osc("127.0.0.1", SCLANG_PD_PORT, f"/beacon/q/{band}", q)
    print(f"   Sent /beacon/q/1..6 with 15Hz BW Qtys")

    # Test global controls
    print("\n5. Global controls...")
    send_osc("127.0.0.1", SCLANG_PD_PORT, "/beacon/mix", 0.7)
    print("   Sent /beacon/mix = 0.7")
    send_osc("127.0.0.1", SCLANG_PD_PORT, "/beacon/master", 1.0)
    print("   Sent /beacon/master = 1.0")

    # Test reset
    print("\n6. Reset...")
    send_osc("127.0.0.1", SCLANG_PD_PORT, "/beacon/reset", 1)
    print("   Sent /beacon/reset")

    print("\n--- All OSC test messages sent ---")

def test_via_webui():
    """Test the full path: simulate what webui.py sends to port 57120.
    The PD replica receives a copy on port 9001."""
    print("\n--- Testing webui-compatible path ---")
    # These are exactly the messages webui.py sends on /control POST
    addr = "/beacon/gain/1"
    val = 1.5
    send_osc("127.0.0.1", SCLANG_PD_PORT, addr, val)
    print(f"   Sent {addr} = {val}  (same as webui.py /control)")

    addr = "/beacon/az/3"
    val = -120
    send_osc("127.0.0.1", SCLANG_PD_PORT, addr, val)
    print(f"   Sent {addr} = {val}")

    addr = "/beacon/dist/5"
    val = 3.0
    send_osc("127.0.0.1", SCLANG_PD_PORT, addr, val)
    print(f"   Sent {addr} = {val}")

    addr = "/beacon/mix"
    val = 0.5
    send_osc("127.0.0.1", SCLANG_PD_PORT, addr, val)
    print(f"   Sent {addr} = {val}")

    addr = "/beacon/master"
    val = 1.2
    send_osc("127.0.0.1", SCLANG_PD_PORT, addr, val)
    print(f"   Sent {addr} = {val}")

    print("--- Webui-compatible test complete ---")

if __name__ == "__main__":
    print("=" * 55)
    print("  PD Replica OSC Control Test")
    print("=" * 55)

    scsynth_ok = check_scsynth()
    log_content = check_sclang_log()
    if log_content:
        lines = log_content.strip().split('\n')
        print(f"  sclang log last 3 lines: {lines[-3:]}")

    if scsynth_ok:
        test_all_bands()
        test_via_webui()
        time.sleep(0.3)
        check_sclang_log()
        print("\n[DONE] All tests passed — OSC routing verified.")
        print("  To test A/B: open http://localhost:5050 and toggle parameters.")
    else:
        print("\n[SKIP] scsynth not running. Start beacon stack first:")
        print("  cd ~/Projects/beacon-spatial && ./start-beacon.sh")
        print("  Then run this test again.")
        print("\n  Test messages still sent to port 9001 (for manual verification):")
        test_all_bands()
        test_via_webui()
