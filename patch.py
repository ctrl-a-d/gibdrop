import subprocess
import sys
import os
import re
import shutil

# Install required dependencies
REQUIRED_PACKAGES = [
    "requests",
    "beautifulsoup4"
]

def install_dependencies():
    print("Installing required Python packages...")
    subprocess.check_call([sys.executable, "-m", "pip", "install"] + REQUIRED_PACKAGES)
    print("Dependencies installed.")

def ensure_run_py():
    if not os.path.exists("run.py"):
        if os.path.exists("example.py"):
            shutil.copy("example.py", "run.py")
            print("run.py not found. Copied example.py to run.py.")
        else:
            print("Neither run.py nor example.py found! Attempting to download example.py from GitHub...")
            import urllib.request
            url = "https://raw.githubusercontent.com/rdavydov/Twitch-Channel-Points-Miner-v2/master/example.py"
            try:
                urllib.request.urlretrieve(url, "example.py")
                print("Downloaded example.py from GitHub.")
                shutil.copy("example.py", "run.py")
                print("Copied downloaded example.py to run.py.")
            except Exception as e:
                print(f"Failed to download example.py: {e}")
                sys.exit(1)

def patch_run_py():
    runpy_path = "run.py"
    if not os.path.exists(runpy_path):
        print("run.py not found!")
        return

    with open(runpy_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Required lines to insert after the last 'from' import for Streamer/StreamerSettings
    required_lines = [
        "from bs4 import BeautifulSoup\n",
        "import get_streamer\n",
        "streamer_names = get_streamer.load_active_streamers()\n",
        "streamer_objects = [Streamer(name) for name in streamer_names]\n"
    ]

    # Insert import/streamer lines if not present
    already_present = any("import get_streamer" in line for line in lines)
    if not already_present:
        insert_idx = None
        for i, line in enumerate(lines):
            if "from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings" in line:
                insert_idx = i + 1
                break
        if insert_idx is not None:
            for offset, req_line in enumerate(required_lines):
                lines.insert(insert_idx + offset, req_line)
            print("Inserted streamer import and loading lines.")

    # Patch the twitch_miner.mine call to use streamer_objects
    # Find the line with 'twitch_miner.mine(' and replace the following lines up to the closing parenthesis
    pattern = re.compile(r"twitch_miner\.mine\s*\(\s*\[", re.DOTALL)
    start_idx = None
    for i, line in enumerate(lines):
        if pattern.search(line):
            start_idx = i
            break
    if start_idx is not None:
        # Find the closing parenthesis for the mine() call
        end_idx = start_idx
        bracket_count = 0
        found_open = False
        for j in range(start_idx, len(lines)):
            if '[' in lines[j]:
                bracket_count += lines[j].count('[')
                found_open = True
            if ']' in lines[j]:
                bracket_count -= lines[j].count(']')
            if found_open and bracket_count == 0:
                # Now look for the closing parenthesis of mine()
                for k in range(j, len(lines)):
                    if ')' in lines[k]:
                        end_idx = k
                        break
                break
        # Replace the block with the new call
        new_call = [
            "twitch_miner.mine(\n",
            "    streamer_objects,                   # Array of streamers (order = priority)\n",
            "    followers=False,                    # Automatic download the list of your followers\n",
            "    followers_order=FollowersOrder.ASC  # Sort the followers list by follow date. ASC or DESC\n",
            ")\n"
        ]
        lines[start_idx:end_idx+1] = new_call
        print("Patched twitch_miner.mine() call to use streamer_objects.")
    else:
        print("No hardcoded streamer list found in twitch_miner.mine(). No changes made to mine() call.")

    with open(runpy_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print("run.py patched successfully!")

def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "--install":
            install_dependencies()
            return
        elif sys.argv[1] == "--patch":
            ensure_run_py()
            patch_run_py()
            return
        else:
            print("Unknown argument. Use --install or --patch.")
            sys.exit(1)
    # If no arguments, show menu
    print("Select an option:")
    print("1) Install dependencies")
    print("2) Patch run.py")
    print("0) Exit")
    choice = input("Enter your choice: ")
    if choice == "1":
        install_dependencies()
    elif choice == "2":
        ensure_run_py()
        patch_run_py()
    elif choice == "0":
        print("Exiting.")
        sys.exit(0)
    else:
        print("Invalid choice.")
        sys.exit(1)

if __name__ == "__main__":
    main()
