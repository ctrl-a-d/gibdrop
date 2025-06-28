import sys
import os
import subprocess
import re
import shutil
import urllib.request

__version__ = "0.0.2"

# --- Bootstrap: install dependencies if missing ---
REQUIRED_PACKAGES = ["requests", "beautifulsoup4"]
VENV_DIR = ".gibdrop_venv"

def in_venv():
    return (
        hasattr(sys, "real_prefix") or
        (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)
    )

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
            for i, name in enumerate(streamer_list):
                if i < len(streamer_list) - 1:
                    f.write(f'Streamer("{name.strip()}")' + ",\n")
                else:
                    f.write(f'Streamer("{name.strip()}")\n')

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
        if not os.path.exists(runpy_path):
            print("run.py not found!")
            return
        with open(runpy_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        required_lines = [
            "from bs4 import BeautifulSoup\n",
            "import get_streamer\n",
            "streamer_names = get_streamer.load_active_streamers()\n",
            "streamer_objects = [Streamer(name) for name in streamer_names]\n"
        ]
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
        pattern = re.compile(r"twitch_miner\.mine\s*\(\s*\[", re.DOTALL)
        start_idx = None
        for i, line in enumerate(lines):
            if pattern.search(line):
                start_idx = i
                break
        if start_idx is not None:
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
                    for k in range(j, len(lines)):
                        if ')' in lines[k]:
                            end_idx = k
                            break
                    break
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
        self.CREDIT_STR = "vibecoded by ctrl-a-d"

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
            yml_exists = any(os.path.isfile(f) for f in ["docker-compose.yml", "docker-compose.yaml"])
            if not yml_exists:
                print("No docker-compose.yml or docker-compose.yaml file found in the current directory.")
                self.press_any_key()
                return
            try:
                result = subprocess.run(['docker', 'compose', 'up', '-d'],
                                        capture_output=True, text=True, check=True)
                print("Docker compose started successfully.")
                print(result.stdout)
            except subprocess.CalledProcessError as e:
                print("Failed to start docker compose:", e)
                print(e.stderr)
            except FileNotFoundError:
                print("Docker is not installed or not found in PATH.")
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
