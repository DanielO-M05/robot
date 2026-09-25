"""
phone_camera_server.py -- self-hosted alternative to a third-party IP
camera app. Runs a tiny local web server on the Pi that serves a page your
phone's browser opens; the page uses the phone's own camera via the
standard getUserMedia web API (no app install) and uploads a frame every
few seconds directly to this server. The server just writes the latest
frame to disk.

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

from pathlib import Path

from flask import Flask, request

FRAME_PATH = Path("/tmp/latest_frame.jpg")
UPLOAD_INTERVAL_MS = 3000  # how often the phone sends a new frame

app = Flask(__name__)

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
        status.textContent = 'Streaming to Pi every {UPLOAD_INTERVAL_MS/1000}s. Keep this open.';
      }})
      .catch(err => {{
        status.textContent = 'Camera access failed: ' + err.message;
      }});

    setInterval(() => {{
      const v = document.getElementById('v');
      const c = document.getElementById('c');
      if (!v.videoWidth) return;
      c.width = v.videoWidth;
      c.height = v.videoHeight;
      c.getContext('2d').drawImage(v, 0, 0);
      c.toBlob(blob => {{
        fetch('/upload', {{method: 'POST', body: blob}});
      }}, 'image/jpeg', 0.8);
    }}, {UPLOAD_INTERVAL_MS});
  </script>
</body>
</html>
"""


@app.route("/")
def index():
    return PAGE


@app.route("/upload", methods=["POST"])
def upload():
    FRAME_PATH.write_bytes(request.data)
    return "", 204


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, ssl_context=("cert.pem", "key.pem"))
