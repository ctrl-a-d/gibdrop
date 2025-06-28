import get_streamer
import os
import subprocess

__version__ = "0.0.1"

ASCII_ART = r"""
          __          __                         
       __/\ \        /\ \                        
   __ /\_\ \ \____   \_\ \  _ __   ___   _____   
 /'_ `\/\ \ \ '__`\  /'_` \/\`'__\/ __`\/\ '__`\ 
/\ \L\ \ \ \ \ \L\ \/\ \L\ \ \ \//\ \L\ \ \ \L\ \
\ \____ \ \_\ \_,__/\ \___,_\ \_\\ \____/\ \ ,__/
 \/___L\ \/_/\/___/  \/__,_ /\/_/ \/___/  \ \ \/ 
   /\____/                                 \ \_\ 
   \_/__/                                   \/_/ 

v.{version}
vibecoded by ctrl-a-d
""".format(version=__version__)

def print_ascii_art():
    print(ASCII_ART)
def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")
def press_any_key():
    input("Press Enter to continue...")
    clear_screen()
def set_active_streamers(filename):
    with open("active_streamers.txt", "w", encoding="utf-8") as f:
        f.write(filename)

def set_default_streamers():
    print("Enter your default streamers (comma separated, e.g. streamer1, streamer2, streamer3):")
    user_input = input("Streamers: ")
    streamer_list = [name.strip() for name in user_input.split(",") if name.strip()]
    if streamer_list:
        get_streamer.save_default_streamers(streamer_list)
        print(f"Saved {len(streamer_list)} default streamers to default_streamer.txt.")
    else:
        print("No streamers entered. Nothing was saved.")
    press_any_key()

def load_default_streamers_menu():
    set_active_streamers("default_streamers.txt")
    print("Default streamers set as active.")
    press_any_key()

def get_drop_streamers():
    rust_streamer_names, general_drops_count = get_streamer.get_rust_drops()

    print("Current Rust Drop Streamers:")
    for name in rust_streamer_names:
        print(name)

    if general_drops_count > 0:
        print(f"\nThere are also {general_drops_count} general drops.")
    else:
        print("\nNo general drops found.")

    get_streamer.save_default_streamers(rust_streamer_names, filename="drop_streamers.txt")
    press_any_key()

def load_drop_streamers_menu():
    set_active_streamers("drop_streamers.txt")
    print("Drop streamers set as active.")
    press_any_key()

def start_twitch_farmer():
    print("How do you want to start the Twitch miner?")
    print("1) Docker")
    print("2) CLI (python run.py)")
    print("0) Cancel")
    choice = input("Enter your choice: ")
    if choice == "1":
        # Check for docker-compose.yml or docker-compose.yaml file
        yml_exists = any(os.path.isfile(f) for f in ["docker-compose.yml", "docker-compose.yaml"])
        if not yml_exists:
            print("No docker-compose.yml or docker-compose.yaml file found in the current directory.")
            press_any_key()
            return
        try:
            # Start docker compose in detached mode
            result = subprocess.run(['docker', 'compose', 'up', '-d'],
                                    capture_output=True, text=True, check=True)
            print("Docker compose started successfully.")
            print(result.stdout)
        except subprocess.CalledProcessError as e:
            print("Failed to start docker compose:", e)
            print(e.stderr)
        except FileNotFoundError:
            print("Docker is not installed or not found in PATH.")
        press_any_key()
    elif choice == "2":
        if not os.path.isfile("run.py"):
            print("run.py not found! Please patch first.")
            press_any_key()
            return
        try:
            result = subprocess.run(["python3", "run.py"])
        except Exception as e:
            print(f"Failed to start run.py: {e}")
        press_any_key()
    else:
        print("Cancelled.")
        press_any_key()

def main():
    while True:
        print_ascii_art()
        print("\nWelcome to gibdrop! Please select an option:")
        print()
        print("1) Install dependencies only")
        print("2) Patch run.py only")
        print("3) Set default streamers")
        print("4) Load default streamers")
        print("5) Get drop streamers")
        print("6) Load drop streamers")
        print("7) Start twitch miner")
        print("0) Exit")
        print()

        choice = input("Enter your choice: ")

        if choice == "1":
            subprocess.run(["python3", "patch.py", "--install"])
            press_any_key()
        elif choice == "2":
            subprocess.run(["python3", "patch.py", "--patch"])
            press_any_key()
        elif choice == "3":
            set_default_streamers()
        elif choice == "4":
            load_default_streamers_menu()
        elif choice == "5":
            get_drop_streamers()
        elif choice == "6":
            load_drop_streamers_menu()
        elif choice == "7":
            start_twitch_farmer()
        elif choice == "0":
            print()
            print("Exiting gibdrop. Goodbye!")
            print()
            break
        else:
            print()
            print("Invalid choice. Please try again.")
            press_any_key()

if __name__ == "__main__":
    main()
