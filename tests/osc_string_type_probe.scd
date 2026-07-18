// Runtime regression probe for SuperCollider's OSC `s` argument decoding.
// Invoked by tests/test_osc_contract.py with sclang listening on a free port.
(
var probePort = "BEACON_OSC_PROBE_PORT".getenv.asInteger;
var caseIndex = 0;
var caseNames = [\missing, \non_string, \osc_string];
var expectedCompatibility = [false, false, true];

OSCdef(\beaconOscStringTypeProbe, { |msg|
  var value = if (msg.size > 1) { msg[1] } { nil };
  var legacyAccepted = (msg.size > 1) and: { value.isKindOf(String) };
  var compatibleAccepted = (msg.size > 1) and: {
    value.isKindOf(String) or: { value.isKindOf(Symbol) }
  };
  var coercedClass = if (compatibleAccepted) { value.asString.class } { nil };

  (
    "[OSC_STRING_PROBE] case=% size=% class=% legacy=% compatible=% coerced=%"
      .format(
        caseNames[caseIndex],
        msg.size,
        value.class,
        legacyAccepted,
        compatibleAccepted,
        coercedClass
      )
  ).postln;

  if (compatibleAccepted != expectedCompatibility[caseIndex]) {
    "[OSC_STRING_PROBE] FAIL".warn;
    1.exit;
  };

  caseIndex = caseIndex + 1;
  if (caseIndex == caseNames.size) {
    SystemClock.sched(0.05, {
      "[OSC_STRING_PROBE] PASS".postln;
      0.exit;
      nil
    });
  };
}, '/beacon/nature/load', nil, probePort);

"[OSC_STRING_PROBE] READY port=%".format(probePort).postln;
SystemClock.sched(10.0, {
  if (caseIndex < caseNames.size) {
    "[OSC_STRING_PROBE] TIMEOUT".warn;
    2.exit;
  };
  nil
});
)
