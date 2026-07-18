// beacon_pd_replica.scd
// SuperCollider replica of the original Pure Data 6-band spatializer.
// Exacts PD math: 6 BPFs with constant 15Hz bandwidth,
// ITD, constant-power panning, 1/dist attenuation,
// butterfly AM (3.7Hz) + pan LFO (0.08Hz, ±90°) on 240Hz band.
//
// Runs as a separate sclang process on port 9001 (same as original PD patch).
// Connects to the same scsynth on 57110 as the main beacon.
// Receives /beacon/* OSC from webui.py (via a bridge process).
//
// Usage:
//   QT_QPA_PLATFORM=offscreen sclang -u 9001 beacon_pd_replica.scd
//
// Band layout (6 bands, 40Hz series, 15Hz constant BW):
//   Band 1:  40 Hz, Q=2.67
//   Band 2:  80 Hz, Q=5.33
//   Band 3: 120 Hz, Q=8.0
//   Band 4: 160 Hz, Q=10.67
//   Band 5: 200 Hz, Q=13.33
//   Band 6: 240 Hz, Q=16.0 (with butterfly AM + pan LFO)

(
var server, synth, oscdefs;
var audioFilePath = "/home/nicolas/Projects/beacon-spatial/harmonic_beacon_2026_05_13_session.wav";
var useFile = "BEACON_SOURCE".getenv == "file";
// SynthDef parameters (declared at top before any statements)
var bpfFreqs = [40, 80, 120, 160, 200, 240];
var defaultQs = [40/15, 80/15, 120/15, 160/15, 200/15, 240/15];  // Q = freq / BW where BW = 15Hz
var defaultGains = [1.2, 1.0, 1.0, 1.0, 1.0, 1.3];
var defaultAz = [180, 135, -90, -45, 45, 0];
var defaultDist = [2.0, 2.5, 3.0, 2.5, 2.0, 1.5];
var dry0 = 0.15, wet0 = 0.85, master0 = 0.9;

// Connect to the existing scsynth on 57110 (same as main beacon)
server = Server(\beacon_pd, NetAddr("127.0.0.1", 57110));
Server.default = server;

"".postln;
"==============================================".postln;
"  BEACON PD REPLICA (6-band, port 9001)      ".postln;
"==============================================".postln;
"SC: %".format(Main.version).postln;
if (useFile) {
  "MODE: FILE — %".format(audioFilePath.basename).postln;
} {
  "MODE: LIVE — SoundIn.ar(0) [R24 CH1]".postln;
};
"".postln;

// Attach to running scsynth
server.startAliveThread(0.4);
server.doWhenBooted({

  // --- Define SynthDef ---
  SynthDef(\beacon_pd_replica, { |out = 0|
    var gains, azs, dists, qs, wet, dry, master;
    var src, drySig, bpfs, butterflyAmp, spatialized;
    var sumLeft, sumRight, wetLeft, wetRight;

    // Band controls: gain (0-3), azimuth (-180..180), distance (0-10)
    gains = defaultGains.collect { |val, i|
      ("gain" ++ (i + 1)).asSymbol.kr(val).lag(0.05)
    };
    azs = defaultAz.collect { |val, i|
      ("az" ++ (i + 1)).asSymbol.kr(val).lag(0.05)
    };
    dists = defaultDist.collect { |val, i|
      ("dist" ++ (i + 1)).asSymbol.kr(val)
    };
    // Q controls
    qs = defaultQs.collect { |val, i|
      ("q" ++ (i + 1)).asSymbol.kr(val)
    };
    // Mix / master
    wet = \wet.kr(wet0);
    dry = \dry.kr(dry0);
    master = \master.kr(master0);

    // Source: file or live input
    if (useFile) {
      var bufnum = \bufnum.kr(0);
      src = PlayBuf.ar(1, bufnum, BufRateScale.kr(bufnum), loop: 1);
    } {
      src = SoundIn.ar(0);
    };

    // Dry path: raw input * dry level
    drySig = src * dry;

    // 6 BPFs with 15Hz constant bandwidth
    bpfs = bpfFreqs.collect { |freq, i|
      BPF.ar(src, freq, qs[i].reciprocal) * gains[i]
    };

    // Butterfly AM: 3.7Hz amplitude modulation on band 6 (240Hz)
    // PD patch: butterfly LFO (3.7Hz) multiplying the 240Hz band
    butterflyAmp = (SinOsc.kr(3.7, 0) * 0.5 + 0.5);  // 0-1 range
    bpfs[5] = bpfs[5] * butterflyAmp;

    // Per-band spatialization
    spatialized = bpfs.collect { |bpfSig, i|
      var azDeg, azRad, d, panLfoAz, panAzRad;
      var panAngle, left, right, amp, sinAz, itdDelay;
      var delayLeft, delayRight;

      azDeg = azs[i];
      azRad = azDeg.degrad;
      d = dists[i].max(0.1);  // avoid div0

      // Pan LFO on band 6: 0.08Hz ±90° around the set azimuth
      // PD patch: [osc~ 0.08] * 90 adds to 240Hz band azimuth
      panLfoAz = if (i == 5) {
        azDeg + (SinOsc.kr(0.08, 0) * 90)
      } {
        azDeg
      };
      panAzRad = panLfoAz.degrad;

      // Constant-power panning (equal amplitude per channel)
      // PD [pan2~]: left = cos(az*pi/4), right = sin(az*pi/4)
      // az ranges from -180..180, map to [-pi/4, pi/4] pan law
      panAngle = panAzRad * 0.25;
      left = cos(panAngle);
      right = sin(panAngle);

      // 1/distance attenuation
      amp = 1 / d;

      // ITD (Interaural Time Difference)
      // PD moses 0 split: sin(az) >= 0 → delay right channel
      //                      sin(az) < 0 → delay left channel
      // delay = |sin(az)| * 0.65 * 5ms (max 3.25ms)
      sinAz = sin(panAzRad);
      itdDelay = abs(sinAz) * 0.65 * 0.005;  // 5ms → seconds
      // BinaryOpUGen for the split (equivalent to PD moses 0)
      delayLeft = (sinAz < 0) * itdDelay;
      delayRight = (sinAz >= 0) * itdDelay;

      // Apply ITD + amplitude
      [DelayN.ar(bpfSig * left * amp, 0.005, delayLeft),
       DelayN.ar(bpfSig * right * amp, 0.005, delayRight)]
    };

    // Sum all bands
    sumLeft = Mix(spatialized.collect { |pair| pair[0] });
    sumRight = Mix(spatialized.collect { |pair| pair[1] });

    // Wet path = spatialized * wet
    wetLeft = sumLeft * wet;
    wetRight = sumRight * wet;

    // Output: wet + dry (mono dry goes to both channels)
    Out.ar(out, [
      (wetLeft + drySig) * master,
      (wetRight + drySig) * master
    ]);
  }).add;

  server.sync;
  "SynthDef \\beacon_pd_replica added.".postln;

  // Load source buffer if file mode
  if (useFile) {
    "Loading buffer: % ...".format(audioFilePath.basename).postln;
    Buffer.read(server, audioFilePath, action: { |buf|
      "  Buffer ready: bufnum=%, % frames, %s".format(
        buf.bufnum, buf.numFrames, buf.duration.round(0.01)
      ).postln;
    });
    server.sync;
  };

  // Create the synth
  synth = Synth(\beacon_pd_replica);
  "Synth active: nodeID=%".format(synth.nodeID).postln;

  // --- OSCdefs ---
  // Map /beacon/gain/N, /beacon/az/N, /beacon/dist/N, /beacon/q/N
  // to the corresponding synth control (gainN, azN, distN, qN)
  oscdefs = [];
  6.do { |i|
    var n = i + 1;

    // /beacon/gain/N  (0-3)
    oscdefs = oscdefs.add(
      OSCdef(
        ("pd_gain_" ++ n).asSymbol,
        { |msg| synth.set(("gain" ++ n).asSymbol, msg[1].asFloat) },
        "/beacon/gain/" ++ n
      )
    );

    // /beacon/az/N   (-180..180)
    oscdefs = oscdefs.add(
      OSCdef(
        ("pd_az_" ++ n).asSymbol,
        { |msg| synth.set(("az" ++ n).asSymbol, msg[1].asFloat) },
        "/beacon/az/" ++ n
      )
    );

    // /beacon/dist/N  (0-10)
    oscdefs = oscdefs.add(
      OSCdef(
        ("pd_dist_" ++ n).asSymbol,
        { |msg| synth.set(("dist" ++ n).asSymbol, msg[1].asFloat) },
        "/beacon/dist/" ++ n
      )
    );

    // /beacon/q/N  (Q value for BPF)
    oscdefs = oscdefs.add(
      OSCdef(
        ("pd_q_" ++ n).asSymbol,
        { |msg| synth.set(("q" ++ n).asSymbol, msg[1].asFloat) },
        "/beacon/q/" ++ n
      )
    );
  };

  // Global controls
  // /beacon/mix  (0-1, wet level)
  oscdefs = oscdefs.add(
    OSCdef(\pd_mix, { |msg|
      var val = msg[1].asFloat;
      synth.set(\wet, val);
      synth.set(\dry, 1 - val);
    }, '/beacon/mix')
  );

  // /beacon/master  (0-3)
  oscdefs = oscdefs.add(
    OSCdef(\pd_master, { |msg|
      synth.set(\master, msg[1].asFloat);
    }, '/beacon/master')
  );

  // /beacon/reset  — restore all defaults
  oscdefs = oscdefs.add(
    OSCdef(\pd_reset, { |msg|
      6.do { |i|
        var n = i + 1;
        synth.set(("gain" ++ n).asSymbol, defaultGains[i]);
        synth.set(("az" ++ n).asSymbol, defaultAz[i]);
        synth.set(("dist" ++ n).asSymbol, defaultDist[i]);
        synth.set(("q" ++ n).asSymbol, defaultQs[i]);
      };
      synth.set(\wet, wet0);
      synth.set(\dry, dry0);
      synth.set(\master, master0);
      "[PD REPLICA RESET] All parameters restored to defaults.".postln;
    }, '/beacon/reset')
  );

  // Placeholder OSCdefs for phase 2 sound-design parameters
  // These accept values but currently do nothing — uncomment when
  // the corresponding controls are added to the SynthDef.

  // /beacon/solo/N  (0 or 1) — not implemented in PD replica yet
  oscdefs = oscdefs.add(
    OSCdef(\pd_solo, { |msg|
      // Placeholder: solo not implemented in PD replica
      // msg[1] is the value, msg[0] is the address string
    }, '/beacon/solo/+')
  );

  // /beacon/record/start — placeholder
  oscdefs = oscdefs.add(
    OSCdef(\pd_record_start, { |msg|
      "[PD REPLICA] Record not yet implemented.".postln;
    }, '/beacon/record/start')
  );

  // /beacon/record/stop — placeholder
  oscdefs = oscdefs.add(
    OSCdef(\pd_record_stop, { |msg|
      "[PD REPLICA] Record not yet implemented.".postln;
    }, '/beacon/record/stop')
  );

  "OSCdefs registered: 24 band + 3 global + 0 solo + 2 record + 1 reset = 30 total.".postln;

  // Cleanup
  ServerQuit.add({
    "[PD REPLICA] Server quit: freeing resources...".postln;
    oscdefs.do { |d| d.free };
    if (synth.notNil) { synth.free };
  }, server);

  // Ready banner
  "".postln;
  "==============================================".postln;
  "  PD REPLICA READY (port 9001)               ".postln;
  "  scsynth:57110  |  OSC in: 9001             ".postln;
  "==============================================".postln;
  "Bands: 40, 80, 120, 160, 200, 240 Hz (15Hz BW)".postln;
  "Initial gains: %".format(defaultGains).postln;
  "Initial az:    % deg".format(defaultAz).postln;
  "Initial dist:  %".format(defaultDist).postln;
  "wet=%, dry=%, master=%".format(wet0, dry0, master0).postln;
  "Butterfly AM: 3.7Hz on 240Hz band".postln;
  "Pan LFO: 0.08Hz ±90° on 240Hz band".postln;
  "ITD: |sin(az)|*0.65*5ms (max 3.25ms)".postln;
  "".postln;
  "Listening on port 9001. Forward OSC from webui.py via bridge.".postln;

});
)
