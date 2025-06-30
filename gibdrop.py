import sys
import os
import subprocess
import re
import shutil
import urllib.request
import gibdrop_dockermgr

__version__ = "0.0.3"

# --- Bootstrap: install dependencies if missing ---
REQUIRED_PACKAGES = ["requests", "beautifulsoup4"]
VENV_DIR = ".gibdrop_venv"

def in_venv():
    return (
        hasattr(sys, "real_prefix") or
        (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)
    )

def ensure_venv_available():
    try:
        import venv
        return True
    except ImportError:
        print("Python 'venv' module is not installed. Attempting to install it...")
        # Try to detect the OS and install venv
        if shutil.which('apt-get'):
            cmd = ['sudo', 'apt-get', 'update']
            try:
                subprocess.check_call(cmd)
            except Exception:
                pass
            cmd = ['sudo', 'apt-get', 'install', '-y', 'python3-venv']
        elif shutil.which('apk'):
            cmd = ['sudo', 'apk', 'add', 'py3-virtualenv']
        elif shutil.which('yum'):
            cmd = ['sudo', 'yum', 'install', '-y', 'python3-venv']
        else:
            print("Could not detect package manager. Please install python3-venv manually.")
            return False
        try:
            subprocess.check_call(cmd)
            import venv
            print("'venv' module installed successfully.")
            return True
        except Exception as e:
            print(f"Failed to install 'venv': {e}\nPlease install python3-venv manually using your system's package manager.")
            return False

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing dependencies. Attempting system install...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + REQUIRED_PACKAGES)
        print("Dependencies installed. Restarting...")
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        print(f"System install failed: {e}\nTrying with a virtual environment...")
        if not in_venv():
            # Create venv if it doesn't exist
            if not os.path.isdir(VENV_DIR):
                if not ensure_venv_available():
                    print("Cannot continue without Python venv support. Exiting.")
                    sys.exit(1)
                print("Creating virtual environment for gibdrop...")
                subprocess.check_call([sys.executable, "-m", "venv", VENV_DIR])
            # Install dependencies in the venv
            pip_path = os.path.join(VENV_DIR, "bin", "pip")
            python_path = os.path.join(VENV_DIR, "bin", "python")
            if os.name == "nt":
                pip_path = os.path.join(VENV_DIR, "Scripts", "pip.exe")
                python_path = os.path.join(VENV_DIR, "Scripts", "python.exe")
            subprocess.check_call([pip_path, "install"] + REQUIRED_PACKAGES)
            print("Restarting script inside virtual environment...")
            os.execv(python_path, [python_path] + sys.argv)
        else:
            print("Failed to install dependencies, even in a virtual environment. Exiting.")
            sys.exit(1)

# StreamerManager: Handles loading, saving, and fetching streamer lists (default, drop, active) for the Twitch miner.
class StreamerManager:
    def get_rust_drops(self):
        url = "https://twitch.facepunch.com/#drops"
        response = requests.get(url)
        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        streamer_drops_div = soup.find('div', class_='streamer-drops')
        if not streamer_drops_div:
            print("Streamer drops section not found!")
            return [], 0
        streamer_names_spans = streamer_drops_div.find_all('span', class_='streamer-name')
        rust_streamer_names = [span.get_text(strip=True) for span in streamer_names_spans]
        drops_div = soup.find('div', id='drops', class_='section drops')
        general_drops_count = 0
        if drops_div:
            h1_title = drops_div.find('h1', class_='title')
            if h1_title:
                span = h1_title.find('span')
                if span:
                    text = span.get_text(strip=True)
                    try:
                        general_drops_count = int(text.strip('()'))
                    except ValueError:
                        general_drops_count = 0
        return rust_streamer_names, general_drops_count

    def save_default_streamers(self, streamer_list, filename="default_streamers.txt"):
        with open(filename, "w", encoding="utf-8") as f:
            for name in streamer_list:
                f.write(f"{name.strip()}\n")

    def load_default_streamers_from_file(self, filename="default_streamers.txt"):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                streamer_names = []
                for line in f:
                    line = line.strip()
                    if line:
                        match = re.match(r'Streamer\("([^\"]+)"\),?', line)
                        if match:
                            streamer_names.append(match.group(1))
                        else:
                            streamer_names.append(line)
                return streamer_names
        except FileNotFoundError:
            return []

    def load_drop_streamers_from_file(self, filename="streamer_names.txt"):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            return []

    def load_active_streamers(self):
        try:
            with open("active_streamers.txt", "r", encoding="utf-8") as f:
                filename = f.read().strip()
            return self.load_default_streamers_from_file(filename)
        except FileNotFoundError:
            return []

# Patcher: Ensures run.py exists and is patched for dynamic streamer loading; manages dependency installation.
class Patcher:
    def __init__(self, required_packages):
        self.required_packages = required_packages

    def install_dependencies(self):
        print("Installing required Python packages...")
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + self.required_packages)
        print("Dependencies installed.")

    def ensure_run_py(self):
        if not os.path.exists("run.py"):
            if os.path.exists("example.py"):
                shutil.copy("example.py", "run.py")
                print("run.py not found. Copied example.py to run.py.")
            else:
                print("Neither run.py nor example.py found! Attempting to download example.py from GitHub...")
                url = "https://raw.githubusercontent.com/rdavydov/Twitch-Channel-Points-Miner-v2/master/example.py"
                try:
                    urllib.request.urlretrieve(url, "example.py")
                    print("Downloaded example.py from GitHub.")
                    shutil.copy("example.py", "run.py")
                    print("Copied downloaded example.py to run.py.")
                except Exception as e:
                    print(f"Failed to download example.py: {e}")
                    sys.exit(1)

    def patch_run_py(self):
        runpy_path = "run.py"
        backup_path = "run.py.bak"
        if not os.path.exists(runpy_path):
            print("run.py not found!")
            return
        # Backup original if not already backed up
        if not os.path.exists(backup_path):
            shutil.copy(runpy_path, backup_path)
            print("Backed up run.py to run.py.bak.")
        with open(runpy_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Find the last occurrence of twitch_miner.mine(
        pattern = re.compile(r"twitch_miner\.mine\s*\(", re.MULTILINE)
        matches = list(pattern.finditer(content))
        if not matches:
            print("No twitch_miner.mine( call found. No changes made.")
            return
        last_match = matches[-1]
        start = last_match.start()
        paren_start = last_match.end() - 1
        # Bracket matching to find the end
        depth = 0
        end = -1
        for i in range(paren_start, len(content)):
            if content[i] == '(': depth += 1
            elif content[i] == ')':
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end == -1:
            print("Could not find matching closing parenthesis for twitch_miner.mine(. No changes made.")
            return
        # Replace the entire function call (from start to end+1)
        replacement = (
            "twitch_miner.mine(\n"
            "    streamer_objects,                   # [gibdrop] patched: dynamic streamer list\n"
            "    followers=False,                    # Automatic download the list of your followers\n"
            "    followers_order=FollowersOrder.ASC  # Sort the followers list by follow date. ASC or DESC\n"
            ")\n"
        )
        new_content = content[:start] + replacement + content[end+1:]
        # Insert import and streamer loading if not present
        import_lines = (
            "import os\n\n"
            "def load_active_streamers():\n"
            "    try:\n"
            "        with open('active_streamers.txt', 'r', encoding='utf-8') as f:\n"
            "            filename = f.read().strip()\n"
            "        with open(filename, 'r', encoding='utf-8') as f2:\n"
            "            return [line.strip() for line in f2 if line.strip()]\n"
            "    except Exception as e:\n"
            "        print(f'Failed to load active streamers: {e}')\n"
            "        return []\n\n"
            "streamer_names = load_active_streamers()\n"
            "streamer_objects = [Streamer(name) for name in streamer_names]\n\n"
        )
        if "streamer_objects = [Streamer(name) for name in streamer_names]" not in new_content:
            # Insert after Streamer import
            streamer_import = "from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings"
            idx = new_content.find(streamer_import)
            if idx != -1:
                insert_idx = new_content.find("\n", idx) + 1
                new_content = new_content[:insert_idx] + import_lines + new_content[insert_idx:]
                print("Inserted streamer loading logic for active_streamers.txt.")
            else:
                print("Could not find Streamer import to insert streamer loading logic. Please check run.py.")
        with open(runpy_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("run.py patched successfully! If anything went wrong, restore from run.py.bak.")

class GibdropMenu:
    def __init__(self, streamer_manager, patcher):
        self.streamer_manager = streamer_manager
        self.patcher = patcher
        self.ASCII_ART = r"""
          __          __                         
       __/\ \        /\ \                        
   __ /\_\ \ \____   \_\ \  _ __   ___   _____   
 /'_ `\/\ \ \ '__`\  /'_` \/\`'__\/ __`\/\ '__`\ 
/\ \L\ \ \ \ \ \L\ \/\ \L\ \ \ \//\ \L\ \ \ \L\ \
\ \____ \ \_\ \_,__/\ \___,_\ \_\\ \____/\ \ ,__/
 \/___L\ \/_/\/___/  \/__,_ /\/_/ \/___/  \ \ \/ 
   /\____/                                 \ \_\ 
   \_/__/                                   \/_/ 
"""
        self.VERSION_STR = f"v.{__version__}"
        self.CREDIT_STR = "vibe coded by ctrl-a-d"

    def print_ascii_art(self):
        print(self.ASCII_ART)
        print(self.VERSION_STR)
        print(self.CREDIT_STR)

    def clear_screen(self):
        os.system("cls" if os.name == "nt" else "clear")

    def press_any_key(self):
        input("Press Enter to continue...")
        self.clear_screen()

    def set_active_streamers(self, filename):
        with open("active_streamers.txt", "w", encoding="utf-8") as f:
            f.write(filename)

    def set_default_streamers(self):
        print("Enter your default streamers (comma separated, e.g. streamer1, streamer2, streamer3):")
        user_input = input("Streamers: ")
        streamer_list = [name.strip() for name in user_input.split(",") if name.strip()]
        if streamer_list:
            self.streamer_manager.save_default_streamers(streamer_list)
            print(f"Saved {len(streamer_list)} default streamers to default_streamer.txt.")
        else:
            print("No streamers entered. Nothing was saved.")
        self.press_any_key()

    def load_default_streamers_menu(self):
        self.set_active_streamers("default_streamers.txt")
        print("Default streamers set as active.")
        self.press_any_key()

    def get_drop_streamers(self):
        rust_streamer_names, general_drops_count = self.streamer_manager.get_rust_drops()
        print("Current Rust Drop Streamers:")
        for name in rust_streamer_names:
            print(name)
        if general_drops_count > 0:
            print(f"\nThere are also {general_drops_count} general drops.")
        else:
            print("\nNo general drops found.")
        # Save as plain usernames, one per line
        self.streamer_manager.save_default_streamers(rust_streamer_names, filename="drop_streamers.txt")
        self.press_any_key()

    def load_drop_streamers_menu(self):
        self.set_active_streamers("drop_streamers.txt")
        print("Drop streamers set as active.")
        self.press_any_key()

    def start_twitch_farmer(self):
        print("How do you want to start the Twitch miner?")
        print("1) Docker")
        print("2) CLI (python run.py)")
        print("0) Cancel")
        choice = input("Enter your choice: ")
        if choice == "1":
            print("\nYou selected Docker. To support your patched run.py and dependencies, gibdrop will build a new Docker image based on the official miner image.\n")
            print("This will ensure your patched run.py and all dependencies work inside Docker.\n")
            gibdrop_dockermgr.ensure_dockerfile()
            gibdrop_dockermgr.ensure_txt_files()
            if gibdrop_dockermgr.needs_rebuild():
                print("No patched Docker image found, or you changed the Dockerfile / dependencies recently.\nNeed to rebuild image.")
                confirm = input("Continue and rebuild image? (y/n): ").strip().lower()
                if confirm != "y":
                    print("Cancelled Docker start.")
                    self.press_any_key()
                    return
                gibdrop_dockermgr.build_image()
            result = gibdrop_dockermgr.run_container()
            if result is False:
                # Docker start was cancelled, user already pressed enter in dockermgr, so just return
                return
            self.press_any_key()
        elif choice == "2":
            if not os.path.isfile("run.py"):
                print("run.py not found! Please patch first.")
                self.press_any_key()
                return
            try:
                result = subprocess.run(["python3", "run.py"])
            except Exception as e:
                print(f"Failed to start run.py: {e}")
            self.press_any_key()
        else:
            print("Cancelled.")
            self.press_any_key()

    def main_menu(self):
        while True:
            self.print_ascii_art()
            print("\nWelcome to gibdrop! Please select an option:")
            print()
            print("1) Patch run.py")
            print("2) Set default streamers")
            print("3) Load default streamers")
            print("4) Get drop streamers")
            print("5) Load drop streamers")
            print("6) Start twitch miner")
            print("0) Exit")
            print()
            choice = input("Enter your choice: ")
            if choice == "1":
                self.patcher.ensure_run_py()
                self.patcher.patch_run_py()
                self.press_any_key()
            elif choice == "2":
                self.set_default_streamers()
            elif choice == "3":
                self.load_default_streamers_menu()
            elif choice == "4":
                self.get_drop_streamers()
            elif choice == "5":
                self.load_drop_streamers_menu()
            elif choice == "6":
                self.start_twitch_farmer()
            elif choice == "0":
                print()
                print("Exiting gibdrop. Goodbye!")
                print()
                break
            else:
                print()
                print("Invalid choice. Please try again.")
                self.press_any_key()

def main():
    streamer_manager = StreamerManager()
    patcher = Patcher(REQUIRED_PACKAGES)
    menu = GibdropMenu(streamer_manager, patcher)
    menu.main_menu()

if __name__ == "__main__":
    main()
