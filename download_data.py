"""Download historical EPL/Championship CSVs from Football-Data.co.uk.

Run locally where internet access is available:
    python -m src.download_data
"""
from pathlib import Path
from urllib.request import urlretrieve

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

SEASONS = ["1617","1718","1819","1920","2021","2122","2223","2324","2425","2526","2627"]
DIVISIONS = {"E0": "premier_league", "E1": "championship"}
BASE = "https://www.football-data.co.uk/mmz4281/{season}/{division}.csv"


def main():
    for season in SEASONS:
        for division, name in DIVISIONS.items():
            url = BASE.format(season=season, division=division)
            out = RAW / f"{name}_{season}.csv"
            try:
                print(f"Downloading {url}")
                urlretrieve(url, out)
            except Exception as e:
                print(f"SKIP {season} {division}: {e}")

if __name__ == "__main__":
    main()
