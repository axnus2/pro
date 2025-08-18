import requests
import json
import re
from datetime import datetime

# Custom headers for the secondary request
SECONDARY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    "Sec-Fetch-Dest": "iframe",
    "Referer": "https://vuen.link/",
}

def log_message(message):
    """Helper function to print formatted log messages"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

def fetch_data(url):
    try:
        log_message(f"Fetching data from API: {url}")
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        response.raise_for_status()
        log_message("API request successful")
        return response.json()
    except requests.exceptions.RequestException as e:
        log_message(f"API request failed: {str(e)}")
        return {'error': f'Request failed: {str(e)}'}
    except json.JSONDecodeError:
        log_message("Invalid JSON response from API")
        return {'error': 'Invalid JSON response'}

def extract_m3u8_url(html_content, channel_name):
    if not html_content:
        log_message(f"No HTML content for {channel_name}")
        return None
    
    try:
        log_message(f"Extracting M3U8 URL for {channel_name}")
        # Clean the HTML
        cleaned_html = (
            html_content
            .replace('","', '')
            .replace(r'\/', '/')
            .replace('////', '//')
        )
        
        # Primary pattern to find the m3u8 URL
        log_message("Trying primary extraction pattern...")
        pattern = r'function\s+trteHltUgp\s*\(\)\s*{[^}]*return\s*\(\s*\["([^"]+)"\]'
        match = re.search(pattern, cleaned_html)
        
        if match:
            m3u8_url = match.group(1)
            log_message(f"Primary pattern successful! Found M3U8: {m3u8_url}")
            return m3u8_url
        
        # Alternative pattern if the first one fails
        log_message("Primary pattern failed, trying alternative...")
        alt_pattern = r'https?://[^\s"\']+\.m3u8[^\s"\']*'
        alt_match = re.search(alt_pattern, cleaned_html)
        if alt_match:
            m3u8_url = alt_match.group(0)
            log_message(f"Alternative pattern successful! Found M3U8: {m3u8_url}")
            return m3u8_url
        
        log_message("Could not find M3U8 URL in HTML content")
        return None
        
    except Exception as e:
        log_message(f"Error extracting M3U8 URL: {str(e)}")
        return None

def get_html_source(url, channel_name):
    try:
        log_message(f"Fetching HTML source for {channel_name} from {url}")
        response = requests.get(url, headers=SECONDARY_HEADERS, timeout=10)
        if response.status_code == 200:
            log_message(f"Successfully fetched HTML for {channel_name}")
            return response.text
        log_message(f"Failed to fetch HTML for {channel_name}. Status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        log_message(f"Request failed for {channel_name}: {str(e)}")
    return None

def format_matches(matches):
    days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    months = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]
    
    result = {}
    
    for match in matches:
        try:
            match_date = datetime.strptime(match['matchDate'], '%Y-%m-%dT%H:%M:%S.%fZ')
            day_name = days[match_date.weekday()]
            day_num = match_date.day
            month_name = months[match_date.month - 1]
            time_str = match_date.strftime('%H:%M')
            
            date_key = f"{day_name} {day_num}th {month_name} - Schedule Time UK GMT"
            
            if date_key not in result:
                result[date_key] = []
            
            channels = []
            for channel in match.get('channels', []):
                channel_name = channel.get('name', 'Unknown Channel')
                original_link = channel.get('links', [None])[0]
                
                if original_link and original_link.startswith('https://vuen.link/ch?id='):
                    log_message(f"\nProcessing channel: {channel_name}")
                    log_message(f"Original link: {original_link}")
                    
                    # Extract channel ID
                    channel_id = original_link.split('=')[1]
                    log_message(f"Extracted channel ID: {channel_id}")
                    
                    # Build embed URL
                    embed_url = f"https://vividmosaica.com/embed3.php?player=desktop&live=do{channel_id}"
                    log_message(f"Built embed URL: {embed_url}")
                    
                    # Get HTML source
                    html_source = get_html_source(embed_url, channel_name)
                    
                    # Extract M3U8 URL
                    m3u8_url = extract_m3u8_url(html_source, channel_name)
                    
                    if m3u8_url:
                        channel_data = {
                            'name': channel_name,
                            'link': m3u8_url,
                            'api': "",
                            'scheme': "0"
                        }
                        channels.append(channel_data)
                        log_message(f"Successfully processed {channel_name}")
                    else:
                        log_message(f"Skipping {channel_name} - no M3U8 URL found")
                
            if channels:
                result[date_key].append({
                    'time': time_str,
                    'event': match.get('league', ''),
                    'channels': channels
                })
                log_message(f"Added match to {date_key}")
                
        except (KeyError, ValueError) as e:
            log_message(f"Error processing match: {str(e)}")
            continue
    
    return result

def save_to_file(data, filename):
    """Save data to a JSON file"""
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        log_message(f"Data successfully saved to {filename}")
    except Exception as e:
        log_message(f"Error saving to file: {str(e)}")

if __name__ == "__main__":
    log_message("Script started")
    url = 'https://s2watch.me/api/v1/schedule/list?detailed=true'
    data = fetch_data(url)
    
    if 'error' in data:
        print(json.dumps(data, indent=2))
        save_to_file(data, 's1.json')
        exit()
    
    if 'matches' not in data:
        error_data = {'error': 'No matches found in response'}
        print(json.dumps(error_data, indent=2))
        save_to_file(error_data, 's1.json')
        exit()
    
    log_message("Formatting matches...")
    formatted_matches = format_matches(data['matches'])
    print("\nFinal Output:")
    print(json.dumps(formatted_matches, indent=2))
    
    # Save the output to s1.json
    save_to_file(formatted_matches, 's1.json')
    log_message("Script completed")
