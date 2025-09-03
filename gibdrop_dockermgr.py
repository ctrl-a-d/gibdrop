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
    "active_streamers.txt",
    "selected_campaigns.txt",
    "rust_drop_streamers.txt"
]

TXT_FILES = [
    "default_streamers.txt",
    "active_streamers.txt",
    "selected_campaigns.txt",
    "rust_drop_streamers.txt"
]

CONTAINER_NAME = "twitch-farmer-gibdrop"

def check_container_status():
    """
    Check the status of the Docker container and display useful information.
    """
    # Check if container exists and get its status
    check_cmd = ["docker", "ps", "-a", "-f", f"name=^{CONTAINER_NAME}$", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"]
    result = subprocess.run(check_cmd, capture_output=True, text=True)
    
    if not result.stdout.strip() or len(result.stdout.strip().split('\n')) < 2:
        print(f"❌ No container named '{CONTAINER_NAME}' found.")
        print("💡 Use option 5 to start the miner.")
        return False
    
    print("🐳 Docker Container Status:")
    print(result.stdout)
    
    # Check if it's running
    running_cmd = ["docker", "ps", "-q", "-f", f"name=^{CONTAINER_NAME}$"]
    running = subprocess.run(running_cmd, capture_output=True, text=True)
    
    if running.stdout.strip():
        print("✅ Container is currently running")
        print("📜 Recent logs:")
        logs_cmd = ["docker", "logs", "--tail", "10", CONTAINER_NAME]
        subprocess.run(logs_cmd)
    else:
        print("⏸️ Container exists but is not running")
        print("💡 Use 'Restart container' to start it with your current streamer list")
    
    return True

def restart_container():
    """
    Restart an existing container to apply new streamer list changes.
    This is much simpler than stop/remove/recreate when you just want to apply config changes.
    """
    # Check if container exists (running or stopped)
    check_cmd = ["docker", "ps", "-a", "-q", "-f", f"name=^{CONTAINER_NAME}$"]
    exists = subprocess.run(check_cmd, capture_output=True, text=True)
    
    if not exists.stdout.strip():
        print(f"❌ No container named '{CONTAINER_NAME}' found.")
        print("💡 Use option 5 to start the miner first.")
        input("Press Enter to continue...")
        return False
    
    print(f"🔄 Restarting container '{CONTAINER_NAME}' to apply new streamer list...")
    
    # Simply restart the container - this will pick up any changes to mounted files
    restart_cmd = ["docker", "restart", CONTAINER_NAME]
    result = subprocess.run(restart_cmd)
    
    if result.returncode == 0:
        print(f"✅ Container '{CONTAINER_NAME}' restarted successfully!")
        print("📋 The miner will now use your updated streamer list.")
        
        # Optional: Show container logs for a few seconds
        print("\n📜 Container logs (press Ctrl+C to stop viewing):")
        try:
            logs_cmd = ["docker", "logs", "-f", "--tail", "20", CONTAINER_NAME]
            subprocess.run(logs_cmd, timeout=10)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            print("\n📋 Container is running. Use 'docker logs -f twitch-famer-gibdrop' to view logs.")
        
        return True
    else:
        print(f"❌ Failed to restart container '{CONTAINER_NAME}'")
        return False

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
    def abs_path_clean(path):
        return os.path.abspath(path).strip()
    # Ensure all .txt files exist before running Docker
    for fname in TXT_FILES:
        if not os.path.exists(fname):
            print(f"[Docker] Creating missing file: {fname}")
            with open(fname, "w", encoding="utf-8") as f:
                f.write("")
    
    # Check if container exists (running or stopped)
    check_cmd = ["docker", "ps", "-a", "-q", "-f", f"name=^{CONTAINER_NAME}$"]
    existing = subprocess.run(check_cmd, capture_output=True, text=True)
    
    if existing.stdout.strip():
        # Container exists - check if it's running
        running_cmd = ["docker", "ps", "-q", "-f", f"name=^{CONTAINER_NAME}$"]
        running = subprocess.run(running_cmd, capture_output=True, text=True)
        
        if running.stdout.strip():
            print(f"A container named '{CONTAINER_NAME}' is already running.")
            resp = input("Stop and remove it before starting a new one? (y/n): ").strip().lower()
        else:
            print(f"A stopped container named '{CONTAINER_NAME}' already exists.")
            resp = input("Remove it and create a new one? (y/n): ").strip().lower()
        
        if resp == "y":
            # Stop if running, then remove
            if running.stdout.strip():
                stop_cmd = ["docker", "stop", CONTAINER_NAME]
                subprocess.run(stop_cmd)
                print(f"Stopped container '{CONTAINER_NAME}'.")
            
            rm_cmd = ["docker", "rm", CONTAINER_NAME]
            subprocess.run(rm_cmd)
            print(f"Removed container '{CONTAINER_NAME}'.")
        else:
            print("Cancelled Docker start. Returning to menu.")
            input("Press Enter to continue...")
            return False
    volumes = [
        f"-v{abs_path_clean('cookies')}:/usr/src/app/cookies",
        f"-v{abs_path_clean('logs')}:/usr/src/app/logs",
        f"-v{abs_path_clean('analytics')}:/usr/src/app/analytics",
        f"-v{abs_path_clean('run.py')}:/usr/src/app/run.py:ro"
    ]
    for fname in TXT_FILES:
        volumes.append(f"-v{abs_path_clean(fname)}:/usr/src/app/{fname}")
    ports = ["-p", "5000:5000"]
    image = FULL_IMAGE
    cmd = ["docker", "run", "-it", "--restart", "unless-stopped", "--name", CONTAINER_NAME] + volumes + ports + [image]
    print("\n[Docker] Running container with persistent cookies/logs/analytics, run.py, and .txt streamer files mounted...")
    print("[Docker] Command:", " ".join(cmd))
    subprocess.run(cmd)
    return True

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
