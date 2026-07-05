# utils/attack_manager.py

import json
import os
import requests
import time
from collections import defaultdict

# --- Configuration ---
DATA_DIR = "db"
ATTACK_JSON_PATH = os.path.join(DATA_DIR, "enterprise-attack.json")
ATTACK_URL = "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"
CACHE_DURATION_DAYS = 30 # How often to re-download the file

def download_attack_data():
    """Downloads the latest enterprise-attack.json from MITRE's GitHub."""
    print("Downloading latest MITRE ATT&CK data... (This may take a moment)")
    try:
        response = requests.get(ATTACK_URL, stream=True)
        response.raise_for_status()
        with open(ATTACK_JSON_PATH, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("Download complete.")
        return True
    except requests.RequestException as e:
        print(f"Error downloading ATT&CK data: {e}")
        return False

def get_attack_data():
    """
    Loads ATT&CK data from a local cache. Downloads if the cache is missing or stale.
    Returns a structured dictionary of tactics and techniques.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Check if the file needs to be downloaded
    needs_download = True
    if os.path.exists(ATTACK_JSON_PATH):
        file_age_seconds = time.time() - os.path.getmtime(ATTACK_JSON_PATH)
        if file_age_seconds < (CACHE_DURATION_DAYS * 24 * 60 * 60):
            needs_download = False
    
    if needs_download:
        if not download_attack_data():
            # If download fails but an old file exists, use it as a fallback
            if os.path.exists(ATTACK_JSON_PATH):
                print("Using stale ATT&CK data as a fallback.")
            else:
                return None # No data available at all

    # Parse the local JSON file
    print("Parsing ATT&CK data...")
    with open(ATTACK_JSON_PATH, "r", encoding="utf-8") as f:
        attack_data = json.load(f)

    # Structure the data for our tree view
    tactics = {}
    techniques_by_tactic = defaultdict(list)

    for item in attack_data["objects"]:
        # First, gather all the tactics
        if item["type"] == "x-mitre-tactic":
            # The shortname is used as a key, e.g., 'initial-access'
            tactics[item["x_mitre_shortname"]] = item["name"]

        # Then, gather techniques and map them to tactics
        elif item["type"] == "attack-pattern" and not item.get("revoked", False):
            if "kill_chain_phases" in item:
                technique_id = next(
                    (eid["external_id"] for eid in item.get("external_references", []) if eid.get("source_name") == "mitre-attack"),
                    None
                )
                if not technique_id:
                    continue
                
                technique_info = {
                    "id": technique_id,
                    "name": item["name"]
                }
                
                for phase in item["kill_chain_phases"]:
                    if phase["kill_chain_name"] == "mitre-attack":
                        tactic_shortname = phase["phase_name"]
                        techniques_by_tactic[tactic_shortname].append(technique_info)

    # Build the final ordered structure
    final_data = []
    for shortname, name in tactics.items():
        if shortname in techniques_by_tactic:
            # Sort techniques alphabetically by name
            sorted_techniques = sorted(techniques_by_tactic[shortname], key=lambda x: x["name"])
            final_data.append({
                "tactic": name,
                "techniques": sorted_techniques
            })
            
    print("ATT&CK data parsing complete.")
    return final_data