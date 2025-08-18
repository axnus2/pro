import requests
import json
from datetime import datetime
from typing import List, Dict, Optional
import base64
from flask import Flask, jsonify

app = Flask(__name__)

# GitHub configuration
GITHUB_TOKEN = "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"
REPO_OWNER = "Daniel-Andress1"
REPO_NAME = "max-x"

def fetch_api_data(api_url: str) -> Optional[Dict]:
    """Fetch JSON data from SonyLIV API"""
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {api_url}: {str(e)}")
        return None

def extract_dai_assets(api_response: Dict) -> List[Dict]:
    """Extract items containing dai_asset_key"""
    extracted_data = []
    
    if not api_response or not api_response.get("resultObj", {}).get("containers"):
        return extracted_data
    
    for container in api_response["resultObj"]["containers"]:
        if container.get("layout") == "CONTENT_ITEM":
            item = process_container(container)
            if item:
                extracted_data.append(item)
        elif container.get("layout") == "portrait_layout" and container.get("assets", {}).get("containers"):
            for asset in container["assets"]["containers"]:
                if asset.get("layout") == "CONTENT_ITEM":
                    item = process_container(asset)
                    if item:
                        extracted_data.append(item)
    
    return extracted_data

def process_container(container: Dict) -> Optional[Dict]:
    """Process container and return data only if it contains dai_asset_key"""
    metadata = container.get("metadata", {})
    emf_attributes = metadata.get("emfAttributes", {})
    
    if not emf_attributes.get("dai_asset_key"):
        return None
    
    # Convert timestamp to readable time if available
    start_time = "00:00"
    if emf_attributes.get("match_start_time"):
        try:
            dt = datetime.fromtimestamp(int(emf_attributes["match_start_time"]))
            start_time = dt.strftime("%H:%M")
        except:
            pass
    
    return {
        "title": metadata.get("title", "N/A"),
        "isLive": metadata.get("isLive", False),
        "audio_languages": emf_attributes.get("audio_languages", "N/A"),
        "tv_background_image": emf_attributes.get("tv_background_image", "N/A"),
        "dai_asset_key": emf_attributes["dai_asset_key"],
        "start_time": start_time,
        "source_api": container.get("_api_source", "N/A")
    }

def generate_api_json(dai_assets: List[Dict]) -> Dict:
    """Generate the API JSON format with empty api field"""
    current_date = datetime.now().strftime("%A %dth %B %Y")
    schedule = {
        f"{current_date} - Schedule Time UK GMT": {
            "Soccer": []
        }
    }
    
    for asset in dai_assets:
        schedule_entry = {
            "time": asset["start_time"],
            "event": f"{asset['title']} - {asset['audio_languages']}",
            "channels": [
                {
                    "name": "Sliv",
                    "link": f"https://dai.google.com/linear/hls/event/{asset['dai_asset_key']}/master.m3u8",
                    "api": "",
                    "scheme": "0"
                }
            ],
            "channels2": []
        }
        schedule[f"{current_date} - Schedule Time UK GMT"]["Soccer"].append(schedule_entry)
    
    return schedule

def generate_max_json(dai_assets: List[Dict]) -> List[Dict]:
    """Generate the Hex JSON format"""
    return [
        {
            "logo": asset["tv_background_image"],
            "name": f"{asset['title']} - {asset['audio_languages']}",
            "link": f"https://dai.google.com/linear/hls/event/{asset['dai_asset_key']}/master.m3u8"
        }
        for asset in dai_assets
    ]

def generate_m3u(dai_assets: List[Dict]) -> str:
    """Generate M3U playlist content"""
    m3u_content = "#EXTM3U\n"
    for asset in dai_assets:
        m3u_content += f"""#EXTINF:-1 tvg-id="{asset['dai_asset_key']}" tvg-name="{asset['title']}" tvg-logo="{asset['tv_background_image']}" group-title="Soccer",{asset['title']} - {asset['audio_languages']}
https://dai.google.com/linear/hls/event/{asset['dai_asset_key']}/master.m3u8
"""
    return m3u_content

def push_to_github(filename: str, content: str, message: str):
    """Push a file to GitHub repository"""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{filename}"
    
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    sha = None
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        sha = response.json().get("sha")
    
    data = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
        "sha": sha
    }
    
    response = requests.put(url, headers=headers, json=data)
    
    if response.status_code in [200, 201]:
        print(f"✅ Successfully pushed {filename} to GitHub")
    else:
        print(f"❌ Failed to push {filename} to GitHub: {response.text}")

@app.route('/')
def home():
    return "SonyLIV DAI Asset Collector is running!"

@app.route('/update', methods=['GET'])
def update():
    api_urls = [
        "https://apiv2.sonyliv.com/AGL/4.7/A/ENG/WEB/IN/UNKNOWN/TRAY/EXTCOLLECTION/30188540?layout=spotlight_layout&id=30188_540",
        "https://apiv2.sonyliv.com/AGL/4.7/A/ENG/WEB/IN/UNKNOWN/TRAY/EXTCOLLECTION/3937924064?layout=portrait_layout&id=39379_24064",
        "https://apiv2.sonyliv.com/AGL/3.5/A/ENG/WEB/IN/UNKNOWN/PAGE-V2/39379_24064?kids_safe=false",
    ]
    
    dai_assets = []
    
    for url in api_urls:
        print(f"🔍 Checking API: {url}")
        api_data = fetch_api_data(url)
        if api_data:
            for container in api_data.get("resultObj", {}).get("containers", []):
                container["_api_source"] = url
            found_assets = extract_dai_assets(api_data)
            if found_assets:
                print(f"✅ Found {len(found_assets)} items with DAI keys")
                dai_assets.extend(found_assets)
                break
    
    if not dai_assets:
        return jsonify({"status": "error", "message": "No DAI assets found"}), 400
    
    # Generate content
    api_json = json.dumps(generate_api_json(dai_assets), indent=2)
    max_json = json.dumps(generate_max_json(dai_assets), indent=2)
    m3u_content = generate_m3u(dai_assets)
    
    # Push files directly to GitHub
    commit_message = f"Update {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    push_to_github("api.json", api_json, commit_message)
    push_to_github("max.json", max_json, commit_message)
    push_to_github("playlist.m3u", m3u_content, commit_message)
    
    return jsonify({
        "status": "success",
        "message": "Files updated successfully",
        "assets_count": len(dai_assets)
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
