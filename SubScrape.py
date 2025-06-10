# SubScrape v1.2 (modified M.A.R.E)
# original script by RK#0102 & Pandela#0001
# now with multi-language support

import os
import re
import sys
import subprocess
# import yt_dlp
from collections import defaultdict
from urllib.parse import quote

vtt_files_dir = 'vtt_files'

def is_clean_line(line):
    """Check if line contains no tags and isn't empty"""
    return not re.search(r'<[^>]+>', line) and line.strip()

def clean_vtt_text(text):
    """Remove all VTT formatting tags from text"""
    return re.sub(r'<[^>]+>', '', text).strip()

def extract_video_id(filename):
    """Extract YouTube video ID from filename (text between square brackets)"""
    match = re.search(r'\[([^\]]+)\]', filename)
    return match.group(1) if match else None

def vtt_timestamp_to_seconds(timestamp):
    """Convert VTT timestamp (HH:MM:SS.mmm) to integer seconds"""
    try:
        hh_mm_ss, millis = timestamp.split('.')
        h, m, s = hh_mm_ss.split(':')
        return int(h) * 3600 + int(m) * 60 + int(s) - 2
    except (ValueError, AttributeError):
        return 0

def update_yt_dlp():
    """Update yt-dlp to the latest version"""
    print("\nUpdating yt-dlp...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"], check=True)
        print("yt-dlp updated successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Error updating yt-dlp: {e}", file=sys.stderr)
        sys.exit(1)

def download_captions(channel_url, include_shorts=False, lang='en'):
    """Download captions for all videos, streams, podcasts, and optionally shorts"""
    base_url = channel_url.rstrip('/')
    endpoints = ['/videos', '/streams', '/podcasts']
    
    if include_shorts:
        endpoints.append('/shorts')
    
    print(f"\nDownloading {lang} captions from:")
    for endpoint in endpoints:
        url = f"{base_url}{endpoint}"
        print(f"  - {url}")
        try:
            subprocess.run([
                'yt-dlp',
                '--write-sub',
                '--sub-lang', lang,
                '--write-auto-sub',
                '--skip-download',
                '--download-archive', 'downloaded.txt',
                '-f', 'best',
                '--sub-format', 'vtt',
                '--convert-subs', 'vtt',
                '-o', f"{vtt_files_dir}/%(title)s [%(id)s].%(ext)s", # copied the default format but added the path
                url
            ], check=True)
            """
            ytdl_opts = {

            }
            """
        except subprocess.CalledProcessError as e:
            print(f"Error downloading from {url}: {e}", file=sys.stderr)
        except FileNotFoundError:
            print("Error: yt-dlp not found. Please install yt-dlp first.", file=sys.stderr)
            sys.exit(1)

def process_vtt_file(vtt_file):
    """Process a single VTT file and return found blocks"""
    try:
        with open(vtt_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(vtt_file, 'r', encoding='ansi') as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading {vtt_file}: {str(e)}", file=sys.stderr)
            return []

    blocks = content.strip().split('\n\n')
    episode = os.path.splitext(vtt_file)[0]
    video_id = extract_video_id(vtt_file)
    found_in_file = []
    seen_text = set()

    for block in blocks:
        if block.startswith(("WEBVTT", "EBVTT", "Kind:", "Language:")):
            continue
            
        lines = block.split('\n')
        if len(lines) < 2:
            continue
            
        time_line = next((line for line in lines if '-->' in line), None)
        if not time_line:
            continue
            
        start_time = time_line.split('-->')[0].strip()
        seconds = vtt_timestamp_to_seconds(start_time)
        
        text_lines = [line.strip() for line in lines[lines.index(time_line)+1:] if is_clean_line(line)]
        
        if not text_lines:
            continue
            
        full_clean_text = " ".join(text_lines)
        
        if full_clean_text in seen_text:
            continue
        seen_text.add(full_clean_text)
        
        found_in_file.append((start_time, seconds, text_lines, episode, vtt_file, video_id))
    
    return found_in_file

def main():
    # Check for update flag
    if "--update" in sys.argv:
        update_yt_dlp()
        sys.argv.remove("--update")  # Remove so it doesn't interfere with search term

    try:
        toFind = " ".join([arg for arg in sys.argv[1:] if arg != "--update"])
        if not toFind:
            raise IndexError
    except IndexError:
        print("""
        USAGE: "python SubScrape.py search_term [--update]"
        
        Options:
          --update    Update yt-dlp before running
          
        VTT files must be in the current directory

        """, file=sys.stderr)
        sys.exit(1)

    # Check for VTT files
    vtt_files = [f for f in os.listdir(vtt_files_dir) if f.lower().endswith('.vtt')]

    if not vtt_files:
        print("No VTT files found in current directory")
        channel_url = input("Enter YouTube channel URL (e.g., https://www.youtube.com/@ChannelName): ").strip()
        if not channel_url:
            print("No URL provided. Exiting.", file=sys.stderr)
            sys.exit(1)
            
        # Language selection prompt
        lang = input("Enter language code (e.g., 'fr' for French, leave empty for English): ").strip().lower()
        if not lang:
            lang = 'en'
            print("Using default language: English")
            
        include_shorts = input("Include /shorts content? (y/n): ").strip().lower() == 'y'
        download_captions(channel_url, include_shorts, lang)
        
        # Refresh file list after download
        vtt_files = [f for f in os.listdir(vtt_files_dir) if f.lower().endswith('.vtt')]
        if not vtt_files:
            print("Still no VTT files found after download attempt. Exiting.", file=sys.stderr)
            sys.exit(1)

    print(f"\nSearching for '{toFind}' in VTT captions:")

    all_found = []
    episodes = set()
    global_seen_text = set()

    for vtt_file in vtt_files:
        file_results = process_vtt_file(f"{vtt_files_dir}/{vtt_file}")
        
        for start_time, seconds, text_lines, episode, filename, video_id in file_results:
            full_clean_text = " ".join(text_lines)
            
            if toFind.lower() in full_clean_text.lower():
                if full_clean_text in global_seen_text:
                    continue
                global_seen_text.add(full_clean_text)
                
                all_found.append((start_time, seconds, text_lines, episode, filename, video_id))
                episodes.add(episode)

    # Output results
    for start_time, seconds, text_lines, episode, filename, video_id in all_found:
        print(f"\nFound in: {filename} ({episode})")
        print(f"{start_time} -->")
        print("\n".join(text_lines))
        
        if video_id:
            yt_url = f"https://www.youtube.com/watch?v={video_id}&t={seconds}"
            print(f"Link: {yt_url}")
        else:
            print("Link: [No YouTube ID found in filename]")

    print(f"\n'{toFind}' found {len(all_found)} unique times in {len(episodes)} files")

if __name__ == "__main__":
    main()