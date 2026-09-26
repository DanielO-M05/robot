"""
phone_camera_server.py -- self-hosted alternative to third-party camera/mic
apps. Runs a tiny local web server on the Pi that serves a page your
phone's browser opens; the page uses the phone's own camera + microphone
via the standard getUserMedia web API (no app install).

VIDEO capture model (on-demand, unchanged from before):
  - The phone's page polls this server every POLL_INTERVAL_MS asking
    "should I capture right now?" A tiny, cheap request, no image involved.
  - When the Pi's code (vision_phone.py) wants a fresh look, it calls
    POST /request_capture on THIS server, which blocks until the phone's
    next poll notices, captures one frame, and POSTs it to /upload. The
    blocked request wakes up and returns those image bytes directly.

AUDIO capture model (voice-activity-gated, NOT continuous chunking):
  - The phone's page runs a simple amplitude-threshold "is someone
    talking" check locally and CONTINUOUSLY, for free (no network call,
    no server involved) using the Web Audio API's AnalyserNode.
  - Only when volume crosses a speech-like threshold does the page start
    recording; it stops and uploads once things go quiet again (POST
    /upload_audio). Actual silence never leaves the phone.
  - Why this matters: Groq's free-tier Whisper is 2,000 requests/day. A
    naive fixed-interval chunk (e.g. every 4s) would burn ~900 req/hour --
    exhausted in ~2.2 hours of continuous testing. Gating on real speech
    keeps usage proportional to how much people actually talk, not to
    wall-clock time.
  - hearing_phone.py (on the Pi) long-polls GET /next_audio_chunk, which
    blocks until a chunk is available (or times out), mirroring the video
    side's request/block/respond shape but pull-based instead of
    push-triggered, since audio chunks arrive at unpredictable times.

Nothing leaves your home network. No third-party app, no cloud service --
just this script, Groq's API (for description/transcription, called from
the Pi side, not from here), and your phone's browser.

Run this in its own terminal/session, separate from run_manual_test.py,
and leave it running the whole time you're testing:

    pip install flask --break-system-packages
    python3 phone_camera_server.py

Then on your phone, in Safari, visit:

    https://<pi-ip>:5000

You'll see a certificate warning (self-signed cert, expected) -- tap
"Show Details" then "visit this website" to proceed. Safe here because
you generated the certificate yourself and stay on your own network.

First, generate the certificate (one-time, skip if you already have one):

    openssl req -x509 -newkey rsa:2048 -nodes \
        -keyout key.pem -out cert.pem -days 365 -subj "/CN=localhost"

Grant camera AND microphone access when Safari prompts you, then leave
that Safari tab open and the phone screen on while you carry it around.
"""

import collections
import threading
from pathlib import Path

from flask import Flask, Response, jsonify, request

FRAME_PATH = Path("/tmp/latest_frame.jpg")     # kept only for debugging/inspection
POLL_INTERVAL_MS = 500                          # how often the phone checks "should I capture video?"
CAPTURE_TIMEOUT_SECONDS = 8.0                   # how long /request_capture waits for a
                                                 # video frame before giving up. Must stay
                                                 # comfortably under whatever timing budget
                                                 # the Pi-side loop expects.
AUDIO_QUEUE_MAXLEN = 5                          # bound the audio backlog; drop oldest on overflow

app = Flask(__name__)

# --- Video: shared state between the polling phone and the requesting Pi code ---
_capture_requested = threading.Event()
_capture_ready = threading.Event()
_latest_frame_bytes = None
_frame_lock = threading.Lock()

# --- Audio: a small FIFO queue the phone pushes to and the Pi pulls from ---
_audio_queue = collections.deque(maxlen=AUDIO_QUEUE_MAXLEN)
_audio_available = threading.Condition()

PAGE = f"""
<!doctype html>
<html>
<body style="margin:0;background:#111;color:#eee;font-family:sans-serif;
             display:flex;align-items:center;justify-content:center;
             height:100vh;text-align:center">
  <div>
    <p id="status">Requesting camera and microphone...</p>
    <video id="v" autoplay playsinline muted style="max-width:90vw"></video>
  </div>
  <canvas id="c" style="display:none"></canvas>
  <script>
    const status = document.getElementById('status');

    // ---------- shared setup ----------
    navigator.mediaDevices.getUserMedia({{video: {{facingMode: 'environment'}}, audio: true}})
      .then(stream => {{
        document.getElementById('v').srcObject = stream;
        status.textContent = 'Ready. Watching for capture requests and listening for speech...';
        pollForVideoRequests();
        startVoiceActivityListening(stream);
      }})
      .catch(err => {{
        status.textContent = 'Camera/mic access failed: ' + err.message;
      }});

    // ---------- video: on-demand capture (unchanged behavior) ----------
    function captureAndUploadFrame() {{
      const v = document.getElementById('v');
      const c = document.getElementById('c');
      if (!v.videoWidth) return Promise.resolve();
      c.width = v.videoWidth;
      c.height = v.videoHeight;
      c.getContext('2d').drawImage(v, 0, 0);
      return new Promise(resolve => {{
        c.toBlob(blob => {{
          fetch('/upload', {{method: 'POST', body: blob}}).then(() => resolve());
        }}, 'image/jpeg', 0.8);
      }});
    }}

    async function pollForVideoRequests() {{
      while (true) {{
        try {{
          const res = await fetch('/should-capture');
          const data = await res.json();
          if (data.capture) {{
            await captureAndUploadFrame();
          }}
        }} catch (err) {{
          // transient network hiccup -- just keep polling
        }}
        await new Promise(r => setTimeout(r, {POLL_INTERVAL_MS}));
      }}
    }}

    // ---------- audio: voice-activity-gated recording ----------
    const SPEECH_THRESHOLD = 12;    // RMS deviation from silence; tune by ear if too sensitive/insensitive
    const SILENCE_HANG_MS = 800;    // how long quiet has to persist before we consider the utterance done
    const MAX_RECORD_MS = 12000;    // hard cap so one long ramble can't record forever

    function pickAudioMimeType() {{
      const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/wav'];
      for (const t of candidates) {{
        if (window.MediaRecorder && MediaRecorder.isTypeSupported(t)) return t;
      }}
      return '';
    }}

    function rms(byteData) {{
      let sum = 0;
      for (let i = 0; i < byteData.length; i++) {{
        const v = byteData[i] - 128;
        sum += v * v;
      }}
      return Math.sqrt(sum / byteData.length);
    }}

    function startVoiceActivityListening(stream) {{
      const audioTrack = stream.getAudioTracks()[0];
      if (!audioTrack) {{
        status.textContent += ' (no microphone track found)';
        return;
      }}
      const micStream = new MediaStream([audioTrack]);
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioCtx.createMediaStreamSource(micStream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 512;
      source.connect(analyser);
      const data = new Uint8Array(analyser.fftSize);
      const mimeType = pickAudioMimeType();

      let recorder = null;
      let chunks = [];
      let isSpeaking = false;
      let silenceTimer = null;
      let maxRecordTimer = null;

      function beginRecording() {{
        isSpeaking = true;
        chunks = [];
        recorder = mimeType ? new MediaRecorder(micStream, {{mimeType}}) : new MediaRecorder(micStream);
        recorder.ondataavailable = e => {{ if (e.data.size > 0) chunks.push(e.data); }};
        recorder.start();
        maxRecordTimer = setTimeout(stopAndUpload, MAX_RECORD_MS);
      }}

      function stopAndUpload() {{
        if (!isSpeaking) return;
        isSpeaking = false;
        clearTimeout(maxRecordTimer);
        if (silenceTimer) {{ clearTimeout(silenceTimer); silenceTimer = null; }}
        recorder.onstop = () => {{
          const blob = new Blob(chunks, {{type: recorder.mimeType || mimeType || 'audio/webm'}});
          fetch('/upload_audio', {{
            method: 'POST',
            headers: {{'Content-Type': blob.type}},
            body: blob
          }});
        }};
        recorder.stop();
      }}

      function tick() {{
        analyser.getByteTimeDomainData(data);
        const level = rms(data);
        if (level > SPEECH_THRESHOLD) {{
          if (!isSpeaking) beginRecording();
          if (silenceTimer) {{ clearTimeout(silenceTimer); silenceTimer = null; }}
        }} else if (isSpeaking && !silenceTimer) {{
          silenceTimer = setTimeout(stopAndUpload, SILENCE_HANG_MS);
        }}
        requestAnimationFrame(tick);
      }}
      tick();
    }}
  </script>
</body>
</html>
"""


@app.route("/")
def index():
    return PAGE


# ---------- video routes (unchanged) ----------

@app.route("/should-capture")
def should_capture():
    return jsonify({"capture": _capture_requested.is_set()})


@app.route("/upload", methods=["POST"])
def upload():
    global _latest_frame_bytes
    if _capture_requested.is_set():
        with _frame_lock:
            _latest_frame_bytes = request.data
        FRAME_PATH.write_bytes(request.data)  # left on disk for debugging only
        _capture_requested.clear()
        _capture_ready.set()
    return "", 204


@app.route("/request_capture", methods=["POST"])
def request_capture():
    """Called by vision_phone.py. Blocks until the phone uploads a fresh frame."""
    _capture_ready.clear()
    _capture_requested.set()
    got_frame = _capture_ready.wait(timeout=CAPTURE_TIMEOUT_SECONDS)
    _capture_requested.clear()

    if not got_frame:
        return "", 504

    with _frame_lock:
        frame_bytes = _latest_frame_bytes
    return Response(frame_bytes, mimetype="image/jpeg")


# ---------- audio routes (new) ----------

@app.route("/upload_audio", methods=["POST"])
def upload_audio():
    mime_type = request.headers.get("Content-Type", "audio/webm")
    with _audio_available:
        _audio_queue.append((request.data, mime_type))
        _audio_available.notify()
    return "", 204


@app.route("/next_audio_chunk")
def next_audio_chunk():
    """
    Called by hearing_phone.py. Long-polls: blocks up to `timeout` seconds
    waiting for a voice-activity-gated chunk to arrive, then returns it.
    Returns 204 if nothing arrived in time -- callers should treat that as
    "nothing heard," not an error.
    """
    timeout = float(request.args.get("timeout", 10.0))
    with _audio_available:
        if not _audio_queue:
            _audio_available.wait(timeout=timeout)
        if not _audio_queue:
            return "", 204
        data, mime_type = _audio_queue.popleft()
    return Response(data, mimetype=mime_type)


if __name__ == "__main__":
    # threaded=True is required: /request_capture and /next_audio_chunk both
    # hold a connection open while blocking, and other routes (/should-capture,
    # /upload, /upload_audio) need to be served concurrently with those waits.
    app.run(host="0.0.0.0", port=5000, ssl_context=("cert.pem", "key.pem"), threaded=True)
