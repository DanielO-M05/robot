"""
Phase 0 echo-delay test: grabs whatever phone_camera_server.py's /next_audio_chunk
hands back and saves it to disk, since the server itself doesn't persist chunks
(they're popped off a queue and handed to whoever asks first).

IMPORTANT: run this INSTEAD OF run_manual_test.py, not alongside it. Both this
script and run_manual_test.py's _hearing_worker thread poll the same
/next_audio_chunk endpoint, and the queue is pop-once -- running both at the same
time means they silently race for chunks and you'll lose some.

Usage:
    python3 capture_audio_chunks.py [server_url] [output_dir]

    python3 capture_audio_chunks.py                       # defaults to https://localhost:5000, ./captured_audio
    python3 capture_audio_chunks.py https://192.168.1.42:5000 ./captured_audio

Leave it running, then in another terminal run:
    paplay test_chirp_reference.wav

Ctrl+C to stop. Each saved chunk is printed with its size and guessed extension
based on the Content-Type the server reported.
"""

import sys
import time
import urllib3
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

EXT_BY_MIME = {
    "audio/webm": "webm",
    "audio/mp4": "mp4",
    "audio/wav": "wav",
    "audio/wave": "wav",
}


def guess_extension(content_type):
    # content_type may be like "audio/webm;codecs=opus" -- strip params
    base = content_type.split(";")[0].strip().lower()
    return EXT_BY_MIME.get(base, "bin")


def main():
    server_url = sys.argv[1] if len(sys.argv) > 1 else "https://localhost:5000"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "./captured_audio"

    import os
    os.makedirs(out_dir, exist_ok=True)

    print(f"Polling {server_url}/next_audio_chunk ... saving to {out_dir}/")
    print("Leave this running, then play the chirp through the speaker in another terminal.")
    print("Ctrl+C to stop.\n")

    index = 0
    while True:
        try:
            resp = requests.get(
                f"{server_url}/next_audio_chunk",
                params={"timeout": 15},
                verify=False,
                timeout=20,
            )
        except requests.exceptions.RequestException as e:
            print(f"Request failed ({e}), retrying...")
            time.sleep(1)
            continue

        if resp.status_code == 204:
            print("  ...no chunk (timed out waiting, nothing heard)")
            continue

        if resp.status_code != 200:
            print(f"  Unexpected status {resp.status_code}, retrying...")
            continue

        content_type = resp.headers.get("Content-Type", "audio/webm")
        ext = guess_extension(content_type)
        filename = f"{out_dir}/chunk_{index:03d}.{ext}"
        with open(filename, "wb") as f:
            f.write(resp.content)

        print(f"  Saved {filename}  ({len(resp.content)} bytes, {content_type})")
        index += 1


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
