# MyVoice AEC3 adapter

A small local binding to the same WebRTC source shipped in `pywebrtc-audio` 0.2.0. It exposes **both** the linear adaptive-filter output and the final residual-echo-suppressed output from one AEC3 instance. This makes speech loss from residual suppression inspectable. It does not add an adaptive algorithm, gate, noise suppression or gain control.

`EchoCanceller(delay_ms=0).process(mic, reference)` accepts contiguous float32 mono arrays of exactly 160 samples at 16 kHz, normalized to [-1, 1]. It returns `(linear, suppressed)`. Instances retain filter state and must be used on one thread. `metrics` reports WebRTC's internal estimates; they do not certify speech preservation. The output paths have different algorithmic latency (64 samples linear, 128 suppressed in this pinned version).

Build/install from the repository root with `uv sync --locked`. Source is included so building does not fetch mutable native code. Linux uses the pinned Zig compiler wheel in the isolated build environment; no system compiler install is necessary. Initial uv setup still downloads build dependencies. No files are patched in site-packages.

The source archive is the unmodified release archive from:
https://github.com/strands-labs/pywebrtc-audio/archive/refs/tags/v0.2.0.tar.gz

SHA256: `be04c2815fed409c3cf64ae70ca267208c3067a155794dd2c09e6e114899ec1f` (checked by CMake).

Upstream license/notice, WebRTC authors/patents and third-party notices remain in the source archive. The installed wheel also carries notices. Upstream's `vendor/webrtc_audio/MODIFICATIONS.md` documents its extracted WebRTC implementation and shims. The local adapter uses that native source without modifying its algorithms; unlike upstream's Python binding it requests `export_linear_aec_output` and passes a separate output buffer to `ProcessCapture`.
