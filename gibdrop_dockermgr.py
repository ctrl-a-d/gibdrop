# NOTE: This script is intended for Linux environments and will not work on Windows.

import subprocess
import os
import sys

DOCKERFILE = "Dockerfile.patched"
IMAGE_NAME = "gibdrop-miner-patched"

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
    print(f"Building Docker image '{IMAGE_NAME}' from {DOCKERFILE}...")
    result = subprocess.run([
        "docker", "build", "-f", DOCKERFILE, "-t", IMAGE_NAME, "."
    ])
    if result.returncode != 0:
        print("Docker build failed!")
        sys.exit(1)
    print("Docker image built successfully.")

def run_container():
    print("Starting patched miner container with mounted files...")
    mounts = []
    for fname in MOUNT_FILES:
        if os.path.exists(fname):
            mounts.extend(["-v", f"{os.path.abspath(fname)}:/usr/src/app/{fname}"])
        else:
            print(f"Warning: {fname} not found, will not be mounted.")
    cmd = ["docker", "run", "-it", "--rm"] + mounts + [IMAGE_NAME]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd)

def ensure_txt_files():
    for fname in TXT_FILES:
        if not os.path.exists(fname):
            print(f"Creating missing file: {fname}")
            with open(fname, "w", encoding="utf-8") as f:
                f.write("")

def needs_rebuild():
    # Check if image exists
    result = subprocess.run(["docker", "images", "-q", IMAGE_NAME], capture_output=True, text=True)
    image_exists = bool(result.stdout.strip())
    if not image_exists:
        return True
    # Check if Dockerfile or requirements.txt changed since last build
    try:
        dockerfile_mtime = os.path.getmtime(DOCKERFILE)
        reqfile = "requirements.txt"
        req_mtime = os.path.getmtime(reqfile) if os.path.exists(reqfile) else 0
        # Get image creation time
        inspect = subprocess.run([
            "docker", "image", "inspect", IMAGE_NAME, "-f", "{{.Created}}"
        ], capture_output=True, text=True)
        import datetime
        from dateutil import parser as dtparser
        image_time = dtparser.parse(inspect.stdout.strip()) if inspect.returncode == 0 and inspect.stdout.strip() else None
        file_time = max(dockerfile_mtime, req_mtime)
        if image_time is None:
            return True
        # Compare file mtime to image creation time
        if datetime.datetime.fromtimestamp(file_time) > image_time:
            return True
    except Exception:
        return True
    return False

def ensure_dockerfile():
    if not os.path.exists(DOCKERFILE):
        print(f"Creating missing Dockerfile: {DOCKERFILE}")
        with open(DOCKERFILE, "w", encoding="utf-8") as f:
            f.write('''FROM rdavidoff/twitch-channel-points-miner-v2:latest\n\nWORKDIR /usr/src/app\n\n# Install extra Python dependencies needed for patched run.py or gibdrop.py\nRUN pip install --no-cache-dir beautifulsoup4 requests\n\n# Entrypoint remains the same as the official image\nENTRYPOINT ["python", "run.py"]\n''')
