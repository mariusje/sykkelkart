#!/usr/bin/env python3
"""
Hjelpescript: Lagrer batch av Strava-aktiviteter fra Claude-output.

BRUK - SCENARIO 1: Kopier-lim fra Claude JSON
═════════════════════════════════════════════════

1. Rett i Claude:
   "Gi meg dette som JSON-array:
    [
      {"id": 19713814940, "dato": "2026-08-12T15:46:12", "navn": "...",
       "sport_type": "Ride", "latlng": [[59.892, 10.611], ...]},
      {"id": 19697303240, "dato": "2026-08-10T...", ...},
      ...
    ]"

2. Kopier responsen (JSON-arrayen)

3. Lagre i temp-fil:
   cat > /tmp/batch.json << 'EOF'
   [{"id": ...}, ...]
   EOF

4. Kjør:
   python3 lagre_batch_aktiviteter.py /tmp/batch.json

═════════════════════════════════════════════════

BRUK - SCENARIO 2: Interaktiv input
════════════════════════════════════

python3 lagre_batch_aktiviteter.py --interactive

Skriptet spør for hver aktivitet og gjør det enkelt å legge inn manuelt.

═════════════════════════════════════

EKSEMPEL BATCH-JSON (kopier fra Claude):

[
  {
    "id": 19713814940,
    "dato": "2026-08-12T15:46:12",
    "navn": "Ettermiddag med sykkeltur",
    "sport_type": "Ride",
    "gear_id": null,
    "latlng": [
      [59.892639, 10.611379],
      [59.893..., 10.612...],
      ...
    ]
  },
  {
    "id": 19697303240,
    "dato": "2026-08-10T14:22:05",
    "navn": "Formiddag løpetur",
    "sport_type": "Run",
    "gear_id": null,
    "latlng": [[60.123, 10.456], ...]
  }
]
"""

import json
import sys
from pathlib import Path
from datetime import datetime

RAW_DIR = Path("data/raw")
HENTET_FILE = Path("data/.aktiviteter_hentet.json")

def lagre_aktiviteter(batch_data):
    """Lagrer batch av aktiviteter som JSON-filer."""
    if not isinstance(batch_data, list):
        print("❌ Feil: JSON må være en liste med aktiviteter")
        return False

    lagret = 0
    feil = 0

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n📝 Lagrer {len(batch_data)} aktiviteter...\n")

    for act in batch_data:
        try:
            # Valider feltene
            required = ["id", "dato", "navn", "sport_type", "latlng"]
            if not all(k in act for k in required):
                print(f"  ❌ {act.get('id', '???')}: Mangler felt {missing}")
                feil += 1
                continue

            # Sjekk at latlng har data
            if not act["latlng"] or len(act["latlng"]) == 0:
                print(f"  ⊘ {act['id']}: Ingen GPS-data (hopper over)")
                feil += 1
                continue

            # Lag filnavn fra dato
            date_str = act["dato"][:10].replace("-", "")
            filename = f"{date_str}_{act['id']}.json"
            filepath = RAW_DIR / filename

            # Lagre JSON
            filepath.write_text(json.dumps(act, ensure_ascii=False, indent=2))

            # Status
            pt_count = len(act["latlng"])
            print(f"  ✓ {filename} ({pt_count} GPS-punkter)")
            lagret += 1

        except Exception as e:
            print(f"  ❌ {act.get('id', '???')}: {e}")
            feil += 1

    print(f"\n{'='*60}")
    print(f"✓ {lagret} aktiviteter lagret")
    if feil > 0:
        print(f"❌ {feil} feil")
    print(f"Total aktiviteter i data/raw: {len(list(RAW_DIR.glob('*.json')))}")

    # Oppdater hentet-liste
    oppdater_hentet_liste()
    return lagret > 0

def oppdater_hentet_liste():
    """Oppdaterer liste over hentet aktiviteter."""
    existing = set()
    for fil in RAW_DIR.glob("*.json"):
        try:
            aid = int(fil.stem.split("_")[1])
            existing.add(aid)
        except (ValueError, IndexError):
            pass

    HENTET_FILE.parent.mkdir(parents=True, exist_ok=True)
    HENTET_FILE.write_text(json.dumps(sorted(existing)))

def fra_fil(filepath):
    """Laster JSON fra fil."""
    print(f"\n📂 Laster fra {filepath}...")
    try:
        data = json.loads(Path(filepath).read_text())
        return data
    except json.JSONDecodeError as e:
        print(f"❌ JSON-feil: {e}")
        return None
    except FileNotFoundError:
        print(f"❌ Fil ikke funnet: {filepath}")
        return None

def interaktiv():
    """Interaktiv batch-entry."""
    print("\n" + "="*60)
    print("🔧 Interaktiv Batch-Entry")
    print("="*60)
    print("Leggi inn aktiviteter manuelt. Skriv 'ferdig' når du er klar.\n")

    batch = []

    while True:
        print(f"\nAktivitet #{len(batch) + 1}")
        aid = input("  Activity ID (eller 'ferdig'): ").strip()

        if aid.lower() == "ferdig":
            break

        try:
            aid = int(aid)
        except ValueError:
            print("  ❌ ID må være et tall")
            continue

        dato = input("  Dato (ISO 8601, f.eks 2026-08-12T15:46:12): ").strip()
        navn = input("  Navn: ").strip()
        sport = input("  Sport Type (Ride/Hike/Run/NordicSki): ").strip()

        print("  Latlng-koordinater (enter når ferdig):")
        latlng = []
        coord_num = 1
        while True:
            coord_str = input(f"    #{coord_num} (lat,lon eller tom): ").strip()
            if not coord_str:
                break
            try:
                lat, lon = map(float, coord_str.split(","))
                latlng.append([lat, lon])
                coord_num += 1
            except ValueError:
                print("    ❌ Format: lat,lon (f.eks 59.892,10.611)")

        if not latlng:
            print("  ⊘ Hopper over - ingen GPS-data")
            continue

        batch.append({
            "id": aid,
            "dato": dato,
            "navn": navn,
            "sport_type": sport,
            "gear_id": None,
            "latlng": latlng
        })

        print(f"  ✓ Lagt til ({len(latlng)} punkter)")

    if batch:
        print(f"\n📝 Lagrer {len(batch)} aktiviteter...")
        lagre_aktiviteter(batch)
    else:
        print("\n⊘ Ingen aktiviteter lagret")

def main():
    if "--interactive" in sys.argv:
        interaktiv()
    elif len(sys.argv) > 1:
        filepath = sys.argv[1]
        data = fra_fil(filepath)
        if data:
            lagre_aktiviteter(data)
    else:
        print(__doc__)
        print("\nEksempel - fra fil:")
        print("  python3 lagre_batch_aktiviteter.py /tmp/batch.json")
        print("\nEksempel - interaktiv:")
        print("  python3 lagre_batch_aktiviteter.py --interactive")

if __name__ == "__main__":
    main()
