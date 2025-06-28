import requests
from bs4 import BeautifulSoup
import re



def get_rust_drops():
    url = "https://twitch.facepunch.com/#drops"
    response = requests.get(url)
    html = response.text

    soup = BeautifulSoup(html, "html.parser")

    # Find the first div that contains the class 'streamer-drops'
    streamer_drops_div = soup.find('div', class_='streamer-drops')

    if not streamer_drops_div:
        print("Streamer drops section not found!")
        return [], 0

    # Extract all streamer names within this section
    streamer_names_spans = streamer_drops_div.find_all('span', class_='streamer-name')
    rust_streamer_names = [span.get_text(strip=True) for span in streamer_names_spans]

    # Find the number of general drops from the General Drops section
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

if __name__ == "__main__":
    rust_streamer_names, general_drops_count = get_rust_drops()

    print("Current Rust Drop Streamers:")
    for name in rust_streamer_names:
        print(name)

    if general_drops_count > 0:
        print(f"\nThere are also {general_drops_count} general drops.")
    else:
        print("\nNo general drops found.")

    # Write the names to a text file, one per line
    with open("drop_streamers.txt", "w", encoding="utf-8") as f:
        for i, name in enumerate(rust_streamer_names):
            if i < len(rust_streamer_names) - 1:
                f.write(f'Streamer("{name}"),\n')
            else:
                f.write(f'Streamer("{name}")\n')

    print(f"\n{len(rust_streamer_names)} streamer names have been saved to 'drop_streamers.txt'.")


def save_default_streamers(streamer_list, filename="default_streamers.txt"):
    with open(filename, "w", encoding="utf-8") as f:
        for i, name in enumerate(streamer_list):
            if i < len(streamer_list) - 1:
                f.write(f'Streamer("{name.strip()}"),\n')
            else:
                f.write(f'Streamer("{name.strip()}")\n')

def load_default_streamers_from_file(filename="default_streamers.txt"):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            streamer_names = []
            for line in f:
                line = line.strip()
                if line:
                    match = re.match(r'Streamer\("([^"]+)"\),?', line)
                    if match:
                        streamer_names.append(match.group(1))
                    else:
                        streamer_names.append(line)
            return streamer_names
    except FileNotFoundError:
        return []
    
def load_drop_streamers_from_file(filename="streamer_names.txt"):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        return []
    
def load_active_streamers():
    try:
        with open("active_streamers.txt", "r", encoding="utf-8") as f:
            filename = f.read().strip()
        return load_default_streamers_from_file(filename)
    except FileNotFoundError:
        return []
