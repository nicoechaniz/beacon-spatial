# Nature Samples Manifest

Field-recording WAVs used by the nature sample layer (`nature/sample_layer.py`,
`/beacon/nature/load`). The WAV files themselves are **not tracked by git**
(see `.gitignore`); this manifest is the tracked record of what belongs here.
To restore a missing sample, re-fetch it from the provenance source and check
it against the SHA-256 below.

Provenance for all entries: `digital-beacon` repo, `data/uploads/` directory —
moved to `beacon-spatial` in task T3.4, 2026-07-18.

| File | Bytes | SHA-256 |
|------|-------|---------|
| `dominicalito_frogs_pond.wav` | 61920102 | `0ddc930613c6f055a7183428140f08269e292b560f2c9e00ddb26bf081f7c072` |
| `06-30-2026 23.52.wav` | 79085670 | `eb70aed787034135883752b6abd565fb3e8270b3f1508e235720ec5d46a256bf` |

Notes:

- `dominicalito_frogs_pond.wav` — frog pond field recording (Dominicalito,
  Costa Rica); the primary nature sample used by SampleLayer.
- `06-30-2026 23.52.wav` — second uploaded WAV; content unreviewed, kept as-is.

Verify after copying/restoring:

```bash
cd assets/nature-samples
sha256sum *.wav
```
