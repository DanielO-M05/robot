"""
phone_camera_server.py -- self-hosted alternative to a third-party IP
camera app. Runs a tiny local web server on the Pi that serves a page your
phone's browser opens; the page uses the phone's own camera via the
standard getUserMedia web API (no app install).

CAPTURE MODEL (on-demand, not continuous streaming):
  - The phone's page polls this server every POLL_INTERVAL_MS asking
    "should I capture right now?" -- a tiny, cheap request, no image
    involved.
  - When the Pi's own code (vision_phone.py) wants a fresh look, it calls
    POST /request_capture on THIS server. That sets a flag, and the
    request blocks (up to CAPTURE_TIMEOUT_SECONDS) until the phone's next
    poll notices the flag, captures exactly one frame, and POSTs it to
    /upload. Once that upload lands, /request_capture wakes up and
    returns those image bytes directly as its response.
  - Net effect: no continuous 3s-interval uploads sitting unused on disk,
    and no fixed staleness window -- every frame the brain ever sees was
    captured within about a second of being asked for.

Nothing leaves your home network. No third-party app, no cloud service --
just this script and your phone's browser.

Run this in its own terminal/session, separate from run_manual_test.py,
and leave it running the whole time you're testing:

    pip install flask --break-system-packages
    python3 phone_camera_server.py

Then on your phone, in Safari, visit:

    https://<pi-ip>:5000

You'll see a certificate warning (self-signed cert, expected) -- tap
"Show Details" then "visit this website" to proceed. This is safe here
specifically because you generated the certificate yourself in the next
step and the connection stays on your own network -- don't get in the
habit of clicking through this warning on other sites.

First, generate the certificate (one-time):

    openssl req -x509 -newkey rsa:2048 -nodes \
        -keyout key.pem -out cert.pem -days 365 -subj "/CN=localhost"

Grant camera access when Safari prompts you, then leave that Safari tab
open and the phone screen on while you carry it around.
"""

import threading
from pathlib import Path

from flask import Flask, Response, jsonify, request

FRAME_PATH = Path("/tmp/latest_frame.jpg")     # kept only for debugging/inspection
POLL_INTERVAL_MS = 500                          # how often the phone checks "should I capture?"
CAPTURE_TIMEOUT_SECONDS = 8.0                   # how long /request_capture waits for a
                                                 # frame before giving up. Must stay
                                                 # comfortably under LOOK_INTERVAL_SECONDS
                                                 # in run_manual_test.py (15s default) --
                                                 # see that file's timing comments.

app = Flask(__name__)

# --- Shared state between the polling phone and the requesting Pi code ---
_capture_requested = threading.Event()   # phone should capture on next poll
_capture_ready = threading.Event()       # a requested frame has arrived
_latest_frame_bytes = None
_frame_lock = threading.Lock()

PAGE = f"""
<!doctype html>
<html>
<body style="margin:0;background:#111;color:#eee;font-family:sans-serif;
             display:flex;align-items:center;justify-content:center;
             height:100vh;text-align:center">
  <div>
    <p id="status">Requesting camera...</p>
    <video id="v" autoplay playsinline muted style="max-width:90vw"></video>
  </div>
  <canvas id="c" style="display:none"></canvas>
  <script>
    const status = document.getElementById('status');

    navigator.mediaDevices.getUserMedia({{video: {{facingMode: 'environment'}}}})
      .then(stream => {{
        document.getElementById('v').srcObject = stream;
        status.textContent = 'Ready. Waiting for the robot to ask for a look...';
        pollLoop();
      }})
      .catch(err => {{
        status.textContent = 'Camera access failed: ' + err.message;
      }});

    function captureAndUpload() {{
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

    async function pollLoop() {{
      while (true) {{
        try {{
          const res = await fetch('/should-capture');
          const data = await res.json();
          if (data.capture) {{
            status.textContent = 'Capturing...';
            await captureAndUpload();
            status.textContent = 'Ready. Waiting for the robot to ask for a look...';
          }}
        }} catch (err) {{
          status.textContent = 'Lost connection to Pi, retrying...';
        }}
        await new Promise(r => setTimeout(r, {POLL_INTERVAL_MS}));
      }}
    }}
  </script>
</body>
</html>
"""


@app.route("/")
def index():
    return PAGE


@app.route("/should-capture")
def should_capture():
    return jsonify({"capture": _capture_requested.is_set()})


@app.route("/upload", methods=["POST"])
def upload():
    global _latest_frame_bytes
    # Ignore uploads that weren't actually requested (e.g. a stray/late
    # poll) so we never serve a frame nobody asked for.
    if _capture_requested.is_set():
        with _frame_lock:
            _latest_frame_bytes = request.data
        FRAME_PATH.write_bytes(request.data)  # left on disk for debugging only
        _capture_requested.clear()
        _capture_ready.set()
    return "", 204


@app.route("/request_capture", methods=["POST"])
def request_capture():
    """
    Called by vision_phone.py (running on the Pi). Blocks until the phone
    captures and uploads a fresh frame, then returns those bytes directly.
    """
    _capture_ready.clear()
    _capture_requested.set()
    got_frame = _capture_ready.wait(timeout=CAPTURE_TIMEOUT_SECONDS)
    _capture_requested.clear()  # in case we timed out and the flag is stale

    if not got_frame:
        return "", 504  # phone didn't respond in time

    with _frame_lock:
        frame_bytes = _latest_frame_bytes
    return Response(frame_bytes, mimetype="image/jpeg")


if __name__ == "__main__":
    # threaded=True is required: /request_capture holds a connection open
    # while it waits, and the phone's /should-capture polling + /upload
    # need to be served concurrently with that wait, not queued behind it.
    app.run(host="0.0.0.0", port=5000, ssl_context=("cert.pem", "key.pem"), threaded=True)
