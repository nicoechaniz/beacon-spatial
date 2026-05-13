# Harmonic Beacon Spatializer

Pure Data patch for 3-band binaural spatialization of the 64Hz harmonic series guitar.

## Files

- `spatializer~.pd` — binaural spatializer abstraction (place in same folder as main patch)
- `beacon-spatial.pd` — main performance patch
- `generate.py` — script that generated both patches (if you need to modify)

## How to use

1. Open `beacon-spatial.pd` in Pure Data (vanilla).
2. DSP should start automatically. If not, press Ctrl+/ (or Cmd+/) to turn on audio.
3. Select your audio interface: **Media > Audio Settings**, set input to Zoom R24 Ch1 and output to your main outs.
4. Plug headphones into the computer (not the R24) to hear the binaural image.
5. Send the computer's stereo output to OBS/YouTube. The R24 output is just the raw guitar.

## What it does

- **LOW** (< 120 Hz): routed rear/ground (default azimuth 170, distance 2)
- **MID** (120-350 Hz): routed front/surface (default azimuth 0, distance 1.5)
- **HIGH** (> 350 Hz): orbiting overhead via LFOs + flutter amplitude modulation (butterflies/fireflies)

The spatialization uses ITD (interaural time difference) + ILD (interaural level difference) for horizontal positioning. Elevation is conveyed by frequency band + distance/brightness.

## Live tweaking

Click any message box and type a new value, then press Enter or click outside:

- `val_low_gain`, `val_mid_gain`, `val_high_gain` — per-band levels
- `val_low_az` / `val_low_dist` — low band position
- `val_mid_az` / `val_mid_dist` — mid band position
- `val_high_az_off` / `val_high_dist_off` — center point for high-band LFOs
- `rate_az` / `rate_dist` — LFO speeds (default 0.08 Hz and 0.05 Hz)
- `master_l` / `master_r` — edit the `*~ 0.8` objects to change master gain

## Important notes for tomorrow

1. **Headphones required.** The binaural effect only works on headphones. Speakers will sound like weird stereo.
2. **YouTube carries the spatial audio well.** Send the stereo output from Pd to your streaming software.
3. **Zoom will flatten it.** Zoom compresses and often mono-mixes. Use YouTube as the primary audio experience.
4. **Latency is low.** The patch uses only 5ms delay buffers and minimal processing. It should feel immediate.
5. **If the R24 is also your output interface**, you may need to use a DAW or Loopback/JACK to route Pd's output to both headphones and the stream. Easiest: use the computer's built-in headphone jack for monitoring, and capture that same output for the stream.

## Troubleshooting

- **No sound?** Check Media > Audio Settings. Make sure the sample rate matches the R24 (usually 44.1k or 48k).
- **Clicks?** Reduce per-band gains or master gain. The 64Hz fundamentals can be very loud.
- **Butterflies too fast/slow?** Edit `rate_az` and `rate_dist` message boxes.
- **Want static high band instead of LFOs?** Disconnect the LFOs and use `val_high_az_off` / `val_high_dist_off` directly into `spat_high`.
