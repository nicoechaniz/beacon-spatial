// beacon.scd
// SuperCollider 3.13 + ATK (Ambisonic Toolkit) 13-band binaural spatializer
// for the Harmonic Beacon (40Hz guitar harmonic series + high harmonics).
//
// PlayBuf (looping harmonic_beacon_2026_05_13_session.wav, mono 48kHz)
//   -> 12x BPF (Q configurable) + 1x HPF (1800Hz) with per-band gain.lag(0.05)
//   -> per-band FoaPanB (az in radians, distance as 1/dist amp scaling)
//   -> sum B-format (WXYZ)
//   -> FoaDecode (Listen kernels, 48000/512) -> wet
//   -> dry = Mix(filter outputs * gains) * (1-mix)
//   -> (wet + dry) * master -> Out.ar(0,2)
//
// OSC (via OSCdef): /beacon/gain/N, /beacon/az/N, /beacon/dist/N (N=1..13),
//                   /beacon/q/N (N=1..12), /beacon/solo/N (N=1..13),
//                   /beacon/mix, /beacon/master
// Lag 0.05 only on gain and azimuth controls per spec.
// Server: 2in/2out, 48000Hz. NO LFOs, NO effects (no Proximity/NFC), NO reverb.
// ONLY FoaPanB + 1/dist scaling for spatialization.
//
// Usage:
//   ./start-beacon.sh
//   (or manually: pw-jack scsynth -u 57110 -i 2 -o 2 &
//                 QT_QPA_PLATFORM=offscreen sclang -u 57120 beacon.scd)
//
// Web UI (Flask) sends OSC /beacon/* to sclang:57120 (OSCdef receivers).
// OSCdefs call synth.set(...) which sends /n_set to scsynth:57110.
//
// Requires: ATK quark + kernels installed at ~/.local/share/ATK/kernels
//           sc3-plugins (for some ATK internals if needed, but core is in ATK)
//
// Band layout:
//   Bands 1-6:  40Hz series, 40Hz bandwidth  [40, 80, 120, 160, 200, 240]
//   Bands 7-12: 240Hz series, 240Hz bandwidth [480, 720, 960, 1200, 1440, 1680]
//   Band 13:    HPF 1800Hz+ (no upper limit)

(
var buf, decoder, synth, oscdefs;
var audioFilePath = "/home/nicolas/Projects/beacon-spatial/harmonic_beacon_2026_05_13_session.wav";

// Use pre-started scsynth (from start-beacon.sh) on standard port 57110.
// sclang listens on 57120 (default or -u) for OSCdef messages from web UI.
var server = Server(\beacon, NetAddr("127.0.0.1", 57110));
Server.default = server;

// --- Server options (informational when scsynth started externally; applied only on boot) ---
server.options.numInputBusChannels = 2;
server.options.numOutputBusChannels = 2;
server.options.sampleRate = 48000;
server.options.memSize = 65536;   // headroom for kernels + buffers
server.options.blockSize = 64;    // default fine; kernel latency ~512/sr anyway

// --- Debug header ---
"".postln;
"========================================".postln;
"  BEACON SPATIALIZER (ATK FOA)          ".postln;
"  12 BPF + 1 HPF binaural (Listen HRTF)".postln;
"========================================".postln;
"SC: %  |  ATK kernels: %".format(Main.version, Atk.userKernelDir).postln;
"Audio file: % (mono, 48kHz)".format(audioFilePath.basename).postln;
"".postln;

// OSC: /beacon/* messages are received by sclang (OSCdef) on its lang port (57120).
// They are translated to .set() calls on the running synth (which talks to scsynth on 57110).
"Send /beacon/gain/N etc OSC to sclang port 57120 (or sclang's -u port).".postln;
"scsynth (audio engine) on 57110 (external, started by start-beacon.sh).".postln;
"Launch via: ./start-beacon.sh".postln;
"".postln;

// --- Attach to running scsynth (no boot attempt; script starts scsynth first) ---
server.startAliveThread(0.4);
server.doWhenBooted({
  // 12 BPF frequencies + HPF cutoff
  var bpfFreqs = [40, 80, 120, 160, 200, 240, 480, 720, 960, 1200, 1440, 1680, 1800];
  // RQ defaults: BW=40Hz for 1-6, BW=240Hz for 7-12
  var defaultRQs = [1.0, 0.5, 1.0/3, 0.25, 0.2, 1.0/6, 0.5, 1.0/3, 0.25, 0.2, 1.0/6, 1.0/7];
  var defaultGains = [1.2, 1.0, 1.0, 1.0, 1.0, 1.3, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0];
  var defaultAz    = [180, 135, -90, -45, 45, 0, 0, 0, 0, 0, 0, 0, 0];
  var defaultDist  = [2.0, 2.5, 3.0, 2.5, 2.0, 1.5, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0];
  var defaultSolo  = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
  var mix0 = 0.85, master0 = 0.9;
  var cond = Condition.new;

  "Server booted (2in/2out @ 48000Hz).".postln;
  server.freeAll;   // clean any prior nodes on re-run

  // Load source buffer (looping WAV)
  "Loading buffer: % ...".format(audioFilePath.basename).postln;
  buf = Buffer.read(server, audioFilePath, action: {
    "  Buffer ready: bufnum=%, % frames, %s".format(
      buf.bufnum, buf.numFrames, buf.duration.round(0.01)
    ).postln;
    cond.unhang;
  });
  cond.hang;

  // Load decoder kernel (Listen subject 1002, explicit 48000/512 path inside ATK)
  "Loading FoaDecoderKernel.newListen(1002, 48000Hz, 512-sample kernels)...".postln;
  decoder = FoaDecoderKernel.newListen(1002, server, 48000);
  // Kernels load async (see 'Kernel HRIR_*.wav, channel * loaded.' posts above)
  2.0.wait;
  "  Decoder kernel ready (allow ~11ms latency from 512-sample HRIR).".postln;

  // Define the core SynthDef
  "Defining SynthDef \\beacon ...".postln;
  SynthDef(\beacon, {
    arg out = 0, bufnum;

    // NamedControls with .lag(0.05) ONLY on azimuth/gain (per spec)
    var gains = defaultGains.collect { |val, i|
      ("gain" ++ (i + 1)).asSymbol.kr(val).lag(0.05)
    };
    var azs = defaultAz.collect { |val, i|
      ("az" ++ (i + 1)).asSymbol.kr(val).lag(0.05)
    };
    var dists = defaultDist.collect { |val, i|
      ("dist" ++ (i + 1)).asSymbol.kr(val)
    };
    var solos = defaultSolo.collect { |val, i|
      ("solo" ++ (i + 1)).asSymbol.kr(val)
    };
    var mix    = \mix.kr(mix0);
    var master = \master.kr(master0);

    // Mono source (looping)
    var src = PlayBuf.ar(
      numChannels: 1,
      bufnum: bufnum,
      rate: BufRateScale.kr(bufnum),
      loop: 1
    );

    var qCtrls = 12.collect { |i|
      ("q" ++ (i + 1)).asSymbol.kr(defaultRQs[i]).lag(0.05)
    };

    // 12x BPF (Q configurable) + 1x HPF (1800Hz, no upper limit)
    var bpfs = bpfFreqs.collect { |freq, i|
      var sig;
      if (i == 12) {
        sig = HPF.ar(src, freq);
      } {
        sig = BPF.ar(src, freq, qCtrls[i]);
      };
      sig * gains[i]
    };

    // Solo logic: if any solo is active, only soloed bands pass
    var anySolo = solos.sum;
    var gates = solos.collect { |s| (anySolo <= 0) + (s * (anySolo > 0)) };
    var gatedBpfs = bpfs.collect { |bpfSig, i| bpfSig * gates[i] };

    // Dry path: Mix(gated filter outputs) * (1-mix)
    var drySig = Mix(gatedBpfs) * (1 - mix);

    // Wet path: per-band FoaPanB(az in rad, distance via 1/dist scaling)
    // Distance scaling applied pre-encode (affects B-format contribution level)
    var foas = gatedBpfs.collect { |bpfSig, i|
      var azRad = azs[i].degrad;
      var d = dists[i].max(0.1);   // avoid div0 / extreme boost at dist=0
      FoaPanB.ar(bpfSig / d, azRad, 0)
    };

    // Sum to single B-format (4 channels: W X Y Z)
    var bfmt = Mix(foas);

    // Decode B-format -> binaural stereo via Listen HRTF kernels
    var wetSig = FoaDecode.ar(bfmt, decoder) * mix;

    // Final wet/dry mix + master
    var sig = (wetSig + drySig) * master;

    Out.ar(out, sig);   // 2 channels
  }).add;

  server.sync;
  "SynthDef \\beacon added.".postln;

  // Instantiate
  synth = Synth(\beacon, [\bufnum, buf.bufnum]);
  "Synth active: nodeID=%  (headphones required for binaural)".format(synth.nodeID).postln;

  // OSCdefs: 13*3 band + 12 q + 13 solo + mix + master = 66 total
  oscdefs = [];
  13.do { |i|
    var n = i + 1;
    oscdefs = oscdefs.add(
      OSCdef(
        ("beacon_gain_" ++ n).asSymbol,
        { |msg| synth.set(("gain" ++ n).asSymbol, msg[1].asFloat) },
        "/beacon/gain/" ++ n
      )
    );
    oscdefs = oscdefs.add(
      OSCdef(
        ("beacon_az_" ++ n).asSymbol,
        { |msg| synth.set(("az" ++ n).asSymbol, msg[1].asFloat) },
        "/beacon/az/" ++ n
      )
    );
    oscdefs = oscdefs.add(
      OSCdef(
        ("beacon_dist_" ++ n).asSymbol,
        { |msg| synth.set(("dist" ++ n).asSymbol, msg[1].asFloat) },
        "/beacon/dist/" ++ n
      )
    );
    if (i < 12) {
      oscdefs = oscdefs.add(
        OSCdef(
          ("beacon_q_" ++ n).asSymbol,
          { |msg| synth.set(("q" ++ n).asSymbol, msg[1].asFloat) },
          "/beacon/q/" ++ n
        )
      );
    };
    oscdefs = oscdefs.add(
      OSCdef(
        ("beacon_solo_" ++ n).asSymbol,
        { |msg| synth.set(("solo" ++ n).asSymbol, msg[1].asFloat) },
        "/beacon/solo/" ++ n
      )
    );
  };
  oscdefs = oscdefs.add(
    OSCdef(\beacon_mix, { |msg| synth.set(\mix, msg[1].asFloat) }, '/beacon/mix')
  );
  oscdefs = oscdefs.add(
    OSCdef(\beacon_master, { |msg| synth.set(\master, msg[1].asFloat) }, '/beacon/master')
  );

  // Recording control
  oscdefs = oscdefs.add(
    OSCdef(\beacon_record_start, { |msg|
      var path = "/home/nicolas/Projects/beacon-spatial/beacon_record_%_%.wav".format(
        Date.localtime.stamp, msg[1].asString
      );
      server.record(path: path, numChannels: 2);
      "[RECORD] Started: %".format(path).postln;
    }, '/beacon/record/start')
  );
  oscdefs = oscdefs.add(
    OSCdef(\beacon_record_stop, { |msg|
      server.stopRecording;
      "[RECORD] Stopped.".postln;
    }, '/beacon/record/stop')
  );

  // Reset control
  oscdefs = oscdefs.add(
    OSCdef(\beacon_reset, { |msg|
      13.do { |i|
        var n = i + 1;
        synth.set(("gain" ++ n).asSymbol, defaultGains[i]);
        synth.set(("az" ++ n).asSymbol, defaultAz[i]);
        synth.set(("dist" ++ n).asSymbol, defaultDist[i]);
        synth.set(("solo" ++ n).asSymbol, 0);
        if (i < 12) {
          synth.set(("q" ++ n).asSymbol, defaultRQs[i]);
        };
      };
      synth.set(\mix, mix0);
      synth.set(\master, master0);
      "[RESET] All parameters restored to defaults.".postln;
    }, '/beacon/reset')
  );

  "OSCdefs registered: 39 band + 12 q + 13 solo + mix + master + record + reset (69 total).".postln;

  // Cleanup hooks
  ServerQuit.add({
    "ServerQuit: freeing beacon resources...".postln;
    oscdefs.do { |d| d.free };
    if (synth.notNil) { synth.free };
    if (decoder.notNil) { decoder.free; "  decoder kernel buffers freed".postln; };
    if (buf.notNil) { buf.free; "  audio buffer freed".postln; };
  }, server);

  CmdPeriod.add({
    "Cmd-. : audio stopped (node freed). Kernel decoder + buffer remain allocated.".postln;
    "        Full cleanup: decoder.free; buf.free;".postln;
  });

  // Final ready banner + defaults
  "".postln;
  "========================================".postln;
  "  BEACON READY                          ".postln;
  "  OSC to sclang:57120 | scsynth:57110   ".postln;
  "========================================".postln;
  "Bands 1-6 : [ 40, 80, 120, 160, 200, 240 ] Hz (40Hz BW)".postln;
  "Bands 7-12: [ 480, 720, 960, 1200, 1440, 1680 ] Hz (240Hz BW)".postln;
  "Band 13   : HPF 1800Hz+".postln;
  "Initial gains: %   (0-3)".format(defaultGains).postln;
  "Initial az:    % deg (-180..180)".format(defaultAz).postln;
  "Initial dist:  %   (0-10)".format(defaultDist).postln;
  "mix=%, master=%".format(mix0, master0).postln;
  "".postln;
  "Signal: PlayBuf -> BPF*12 + HPF*1 -> FoaPanB(az.rad, 1/dist) -> B-format".postln;
  "        -> FoaDecode(Listen) = wet   |   Mix(filters*gains) * (1-mix)".postln;
  "        -> (wet + dry) * master -> stereo out".postln;
  "".postln;
"No LFOs, no reverb, no extra effects (plain FoaPanB + 1/dist only).".postln;
"To stop: ctrl-. (or s.quit; decoder.free; buf.free; 0.exit; )".postln;
"".postln;

// Keep sclang alive (OSCdefs remain active)
"sclang waiting for OSC...".postln;
});
)
