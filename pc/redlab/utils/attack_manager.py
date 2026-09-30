# utils/attack_manager.py

"""MITRE ATT&CK data access.

The upstream enterprise-attack.json is ~45.7 MB across ~26,000 objects, of
which only the 15 tactics and 858 attack-patterns are used. Parsing the whole
file blocked the GUI thread for several seconds on every launch and peaked at
several hundred megabytes, so two changes matter here:

  1. A compact cache is written next to the dataset holding only the tactics and
     techniques. Startup reads that (a few hundred KB) instead of 45.7 MB. The
     big file is parsed once, when it is first refreshed.
  2. Nothing here touches the GUI thread any more. CampaignsPanel loads on a
     worker; see ui/panels/campaigns.py.
"""

import json
import os
import time
from collections import defaultdict

# --- Configuration ---
# Resolved against this file, not the working directory. DATA_DIR used to be the
# bare relative string "db", so launching the app from anywhere other than pc/
# silently created a second cache directory and re-downloaded 45.7 MB.
# redlab/utils/attack_manager.py -> redlab/ -> pc/
_APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(_APP_ROOT, "db")

ATTACK_JSON_PATH = os.path.join(DATA_DIR, "enterprise-attack.json")
COMPACT_PATH = os.path.join(DATA_DIR, "enterprise-attack.compact.json")
ATTACK_URL = "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"

CACHE_DURATION_DAYS = 30          # How often to re-download the file
DOWNLOAD_TIMEOUT = 20             # Seconds. Was unbounded, so a dead network
                                   # froze the UI until the OS TCP timeout.
DOWNLOAD_CHUNK = 256 * 1024       # 8 KB chunks made a 45.7 MB write take ~5,700 syscalls

COMPACT_FORMAT_VERSION = 2


def _file_age_seconds(path):
    try:
        return time.time() - os.path.getmtime(path)
    except OSError:
        return None


def _is_fresh(path):
    age = _file_age_seconds(path)
    return age is not None and age < (CACHE_DURATION_DAYS * 24 * 60 * 60)


def download_attack_data(progress=None):
    """Download the dataset to a temp file, then move it into place.

    Writing straight to ATTACK_JSON_PATH meant an interrupted download left a
    truncated file that looked valid on the next run. The rename is atomic, so
    a failed transfer never replaces a good cache.
    """
    print("Downloading latest MITRE ATT&CK data... (This may take a moment)")
    tmp_path = ATTACK_JSON_PATH + ".part"
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        import requests
    except ImportError:
        print("requests is not installed; cannot refresh ATT&CK data.")
        return False

    try:
        with requests.get(ATTACK_URL, stream=True, timeout=DOWNLOAD_TIMEOUT) as response:
            response.raise_for_status()
            total = int(response.headers.get("Content-Length") or 0)
            written = 0
            with open(tmp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK):
                    if not chunk:
                        continue
                    f.write(chunk)
                    written += len(chunk)
                    if progress and total:
                        progress(written, total)
        os.replace(tmp_path, ATTACK_JSON_PATH)
        print("Download complete.")
        return True
    except Exception as e:
        # Broad on purpose: requests.RequestException did not cover timeouts
        # raised by the OS, nor a full disk.
        print(f"Error downloading ATT&CK data: {e}")
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        return False


def _build_from_dataset():
    """Parse the full dataset into the compact structure."""
    print("Parsing ATT&CK data...")
    with open(ATTACK_JSON_PATH, "r", encoding="utf-8") as f:
        attack_data = json.load(f)

    tactics = {}
    techniques_by_tactic = defaultdict(list)

    for item in attack_data["objects"]:
        item_type = item.get("type")
        if item_type == "x-mitre-tactic":
            tactics[item["x_mitre_shortname"]] = item["name"]
        elif item_type == "attack-pattern" and not item.get("revoked", False):
            kill_chain = item.get("kill_chain_phases")
            if not kill_chain:
                continue
            technique_id = next(
                (
                    ref.get("external_id")
                    for ref in item.get("external_references", [])
                    if ref.get("source_name") == "mitre-attack"
                ),
                None,
            )
            if not technique_id:
                continue

            technique_info = {"id": technique_id, "name": item["name"]}
            for phase in kill_chain:
                if phase.get("kill_chain_name") == "mitre-attack":
                    techniques_by_tactic[phase["phase_name"]].append(technique_info)

    final_data = []
    for shortname, name in tactics.items():
        if shortname in techniques_by_tactic:
            final_data.append({
                "tactic": name,
                "techniques": sorted(techniques_by_tactic[shortname], key=lambda x: x["name"]),
            })

    print("ATT&CK data parsing complete.")
    return final_data


def _write_compact(tactics):
    """Persist the extracted subset so later launches skip the 45.7 MB parse."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = COMPACT_PATH + ".part"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(
                {"version": COMPACT_FORMAT_VERSION, "built": time.time(), "tactics": tactics},
                f,
            )
        os.replace(tmp, COMPACT_PATH)
        return True
    except OSError as e:
        # A missing compact cache only costs time on the next start.
        print(f"Could not write ATT&CK compact cache: {e}")
        return False


def _read_compact():
    try:
        with open(COMPACT_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, ValueError):
        return None

    if not isinstance(payload, dict):
        return None
    if payload.get("version") != COMPACT_FORMAT_VERSION:
        return None

    tactics = payload.get("tactics")
    if not isinstance(tactics, list) or not tactics:
        return None
    return tactics


def get_attack_data(progress=None, allow_download=True):
    """Return the ATT&CK tactic/technique structure, or None if unavailable.

    Order of preference:
      1. the compact cache, when it is newer than the dataset
      2. the compact cache, when it is fresh even if the dataset is newer
      3. parse the dataset and rewrite the compact cache
      4. download, then parse
    """
    os.makedirs(DATA_DIR, exist_ok=True)

    dataset_age = _file_age_seconds(ATTACK_JSON_PATH)
    dataset_fresh = dataset_age is not None and dataset_age < (CACHE_DURATION_DAYS * 24 * 60 * 60)
    compact_age = _file_age_seconds(COMPACT_PATH)

    cached = _read_compact()
    if cached is not None:
        # Rebuild only when the dataset is genuinely newer than the index.
        # Both values are ages, so a *smaller* age means a more recent file.
        dataset_is_newer = dataset_age is not None and (
            compact_age is None or dataset_age < compact_age
        )
        needs_rebuild = dataset_fresh and dataset_is_newer
        if not needs_rebuild:
            return cached
        print("ATT&CK dataset updated, rebuilding index...")
        tactics = _build_from_dataset()
        _write_compact(tactics)
        return tactics

    # No usable compact cache: fall back to the dataset itself.
    if dataset_age is not None:
        if not dataset_fresh and allow_download:
            print("ATT&CK dataset is stale, refreshing...")
            download_attack_data(progress=progress)
        tactics = _build_from_dataset()
        _write_compact(tactics)
        return tactics

    if allow_download:
        download_attack_data(progress=progress)
        if os.path.exists(ATTACK_JSON_PATH):
            tactics = _build_from_dataset()
            _write_compact(tactics)
            return tactics

    return None
