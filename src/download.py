"""Download the raw data used by the project.

Sources (all open data, Licence Ouverte / Etalab 2.0):
  * ONISR road-accident database (BAAC), 2019-2024, four tables per year
    https://www.data.gouv.fr/datasets/bases-de-donnees-annuelles-des-accidents-corporels-de-la-circulation-routiere-annees-de-2005-a-2024/
  * INSEE population estimates by department, sex and age group (1975-2023)
  * French department boundaries (simplified GeoJSON, gregoiredavid/france-geojson)

Run:  python src/download.py
Files land in data/raw/. Already-downloaded files are skipped.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
YEARS = range(2019, 2025)
TABLES = ("caract", "lieux", "vehicules", "usagers")
DATASET_API = ("https://www.data.gouv.fr/api/1/datasets/"
               "bases-de-donnees-annuelles-des-accidents-corporels-de-la-circulation-routiere-annees-de-2005-a-2024/")
EXTRA = {
    "insee_pop_dep.xls": "https://www.insee.fr/fr/statistiques/fichier/1893198/estim-pop-dep-sexe-aq-1975-2023.xls",
    "departements.geojson": "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements-version-simplifiee.geojson",
    "communes-68.geojson": "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements/68-haut-rhin/communes-68-haut-rhin.geojson",
}


def fetch(url: str, dest: Path, tries: int = 8) -> None:
    """Download url to dest, retrying on network errors (open-data servers are flaky)."""
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                data = r.read()
            dest.write_bytes(data)
            print(f"  ok   {dest.name} ({len(data)/1e6:.1f} MB)")
            return
        except Exception as e:  # noqa: BLE001 - we only want to retry
            print(f"  retry {attempt}/{tries} {dest.name}: {e}")
            time.sleep(3 * attempt)
    raise RuntimeError(f"could not download {url}")


def baac_urls() -> dict[str, str]:
    """Ask the data.gouv.fr API for the current URL of every yearly table."""
    meta = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(DATASET_API, timeout=60) as r:
                meta = json.load(r)
            break
        except Exception:
            time.sleep(3)
    if meta is None:
        raise RuntimeError("data.gouv.fr API unreachable")
    urls = {}
    for res in meta["resources"]:
        title = res["title"].lower()
        m = re.search(r"(20\d\d)", title)
        if not m or "immatric" in title or not title.endswith(".csv"):
            continue
        year = int(m.group(1))
        if year not in YEARS:
            continue
        for t in TABLES:
            # the 2021/2022 "caracteristiques" file is spelled "carcteristiques"
            if title.startswith(t) or (t == "caract" and title.startswith("carct")):
                urls[f"{t}-{year}.csv"] = res["url"]
    return urls


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    todo = {**baac_urls(), **EXTRA}
    missing = [f"{t}-{y}.csv" for y in YEARS for t in TABLES if f"{t}-{y}.csv" not in todo]
    if missing:
        raise RuntimeError(f"tables not found in the API listing: {missing}")
    for name, url in sorted(todo.items()):
        dest = RAW / name
        if dest.exists() and dest.stat().st_size > 1000:
            continue
        fetch(url, dest)


if __name__ == "__main__":
    main()
