# NOTE: This script is intended for Linux environments and will not work on Windows.

import subprocess
import os
import sys

DOCKERFILE = "Dockerfile.patched"
# Use a single, consistent image name everywhere
IMAGE_NAME = "gibdrop-miner-patched"
IMAGE_TAG = "latest"
FULL_IMAGE = f"{IMAGE_NAME}:{IMAGE_TAG}"

# Files to mount (edit as needed)
MOUNT_FILES = [
    "run.py",
    "default_streamers.txt",
    "drop_streamers.txt",
    "active_streamers.txt"
]

TXT_FILES = [
    "default_streamers.txt",
    "drop_streamers.txt",
    "active_streamers.txt"
]

def build_image():
    print(f"Building Docker image '{FULL_IMAGE}' from {DOCKERFILE}...")
    result = subprocess.run([
        "docker", "build", "-f", DOCKERFILE, "-t", FULL_IMAGE, "."
    ])
    if result.returncode != 0:
        print("Docker build failed!")
        sys.exit(1)
    print("Docker image built successfully.")

def run_container():
    import subprocess
    import os
    # Ensure persistent volumes for cookies, logs, analytics, and mount run.py as read-only
    def abs_path_clean(path):
        return os.path.abspath(path).strip()
    # Ensure all .txt files exist before running Docker
    for fname in TXT_FILES:
        if not os.path.exists(fname):
            print(f"[Docker] Creating missing file: {fname}")
            with open(fname, "w", encoding="utf-8") as f:
                f.write("")
    volumes = [
        f"-v{abs_path_clean('cookies')}:/usr/src/app/cookies",
        f"-v{abs_path_clean('logs')}:/usr/src/app/logs",
        f"-v{abs_path_clean('analytics')}:/usr/src/app/analytics",
        f"-v{abs_path_clean('run.py')}:/usr/src/app/run.py:ro"
    ]
    # Mount all .txt streamer files as well
    for fname in TXT_FILES:
        volumes.append(f"-v{abs_path_clean(fname)}:/usr/src/app/{fname}")
    ports = ["-p", "5000:5000"]
    image = FULL_IMAGE
    cmd = ["docker", "run", "-it", "--rm"] + volumes + ports + [image]
    print("\n[Docker] Running container with persistent cookies/logs/analytics, run.py, and .txt streamer files mounted...")
    print("[Docker] Command:", " ".join(cmd))
    subprocess.run(cmd)

def ensure_txt_files():
    for fname in TXT_FILES:
        if not os.path.exists(fname):
            print(f"Creating missing file: {fname}")
            with open(fname, "w", encoding="utf-8") as f:
                f.write("")

def needs_rebuild():
    # Check if image exists using docker image inspect
    result = subprocess.run([
        "docker", "image", "inspect", FULL_IMAGE
    ], capture_output=True, text=True)
    if result.returncode != 0:
        return True
    # Check if Dockerfile or requirements.txt changed since last build
    try:
        import datetime
        try:
            from dateutil import parser as dtparser
        except ImportError:
            print("[DEBUG] dateutil not found, falling back to datetime.fromisoformat (Python 3.7+ required)")
            dtparser = None
        dockerfile_mtime = os.path.getmtime(DOCKERFILE)
        reqfile = "requirements.txt"
        req_mtime = os.path.getmtime(reqfile) if os.path.exists(reqfile) else 0
        # Get image creation time
        inspect = subprocess.run([
            "docker", "image", "inspect", FULL_IMAGE, "-f", "{{.Created}}"
        ], capture_output=True, text=True)
        if dtparser:
            image_time = dtparser.parse(inspect.stdout.strip()) if inspect.returncode == 0 and inspect.stdout.strip() else None
        else:
            image_time = datetime.datetime.fromisoformat(inspect.stdout.strip().replace('Z', '+00:00')) if inspect.returncode == 0 and inspect.stdout.strip() else None
        file_time = max(dockerfile_mtime, req_mtime)
        if image_time is None:
            return True
        file_datetime = datetime.datetime.fromtimestamp(file_time, tz=image_time.tzinfo)
        if file_datetime > image_time:
            return True
    except Exception as e:
        print(f"[DEBUG] Time comparison failed: {e}")
        return True
    return False

def ensure_dockerfile():
    if not os.path.exists(DOCKERFILE):
        print(f"Creating missing Dockerfile: {DOCKERFILE}")
        with open(DOCKERFILE, "w", encoding="utf-8") as f:
            f.write('''FROM rdavidoff/twitch-channel-points-miner-v2:latest\n\nWORKDIR /usr/src/app\n\n# Install extra Python dependencies needed for patched run.py or gibdrop.py\nRUN pip install --no-cache-dir beautifulsoup4 requests\n\n# Entrypoint remains the same as the official image\nENTRYPOINT ["python", "run.py"]\n''')
