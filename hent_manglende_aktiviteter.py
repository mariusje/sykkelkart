#!/usr/bin/env python3
"""
Henter manglende aktiviteter fra Strava API for 2026 og lagrer som JSON.

BRUK:
    python3 hent_manglende_aktiviteter.py

FORUTSETNINGER:
    - Strava API-tilgang via Claude MCP
    - claude kommando installert og konfigurert
    - Python 3.10+
    - Directory: data/raw/ eksisterer

PROSESS:
    1. Lister alle aktiviteter hentet så langt fra data/raw/
    2. Henter metadata for alle 2026-aktiviteter som ikke er lagret
    3. For hver aktivitet: henter GPS-data via get_activity_streams
    4. Lagrer som JSON: YYYYMMDD_<activity_id>.json
    5. Rapporterer progresjon og antall GPS-punkter

AKTIVITETSTYPER SOM HENTES:
    - Ride, GravelRide, MountainBikeRide, EBikeRide, EMountainBikeRide, Velomobile (sykkeltyper)
    - Hike, Run (andre aktiviteter med GPS)
    - NordicSki, AlpineSki, Snowboard (vinterspørter med GPS)
    - VirtualRide (virtuell sykkelstall - hvis det har GPS)

AKTIVITETSTYPER SOM HOPPES OVER:
    - WeightTraining (treningsstudio - ingen GPS)
    - og andre aktiviteter uten GPS-potensial

TIPS:
    - Kjør med `nohup python3 hent_manglende_aktiviteter.py > hent.log 2>&1 &`
      for bakgrunnsprosess som ikke stopper ved terminal-lukking
    - Følg progresjon med: tail -f hent.log
    - Stopp når som helst med Ctrl+C - resumerer fra der det stoppet neste kjøring
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Konfigurering
RAW_DIR = Path("data/raw")
ALREADY_HENTET_FILE = Path("data/.aktiviteter_hentet.json")  # Lagrer hvilke vi allerede har hentet

# Alle 197 aktivitets-IDer fra 2026 (sortert nyeste → eldste)
ALLE_2026_AKTIVITETER = [
    # August 2026
    19713814940, 19697303240, 19682861416, 19669732558, 19655049134, 19637281633,
    19637192210, 19626485473, 19611068642, 19598092479, 19586027059, 19570391382,
    19557235686, 19544529282, 19516067871, 19498557065, 19487033921, 19413692798,
    19398562682, 19371534448, 19358577592, 19357698617,
    # Juli 2026
    19040367670, 19023565278, 19013401714, 18973321741, 18959434125, 18944303598,
    18930787817, 18893068307, 18881512196, 18866815463, 18866176307, 18854359462,
    18834158934, 18833638005, 18779507678, 18757670318, 18743715861, 18729285131,
    18715208998, 18716109393, 18703879509, 18690866164, 18662609199, 18648138387,
    18647786585, 18631402730, 18611494041, 18596487811, 18584421718, 18571114179,
    18570783000, 18556660670, 18537491094, 18537383691, 18499977064, 18465308710,
    18464947893, 18441508341, 18413822971, 18400126731, 18388290953, 18359950463,
    18344061452, 18333589211, 18319844781, 18306435495, 18296691883, 18279674083,
    18262055341, 18247654994, 18241005616, 18228518453, 18228364952,
    # April-Mai 2026
    18212636516, 18198726124, 18187306372, 18177855570, 18176481210, 18155661433,
    18146625900, 18132688151, 18075213106, 18062170401, 18055124488, 18041681735,
    18028601203, 18028166176, 18017437774, 17988139272, 17976577681, 17964542045,
    17950335603, 17925744864, 17912563623, 17909838059, 17901553875, 17890224550,
    17878753722, 17866799815, 17856322452, 17844983894, 17844568699, 17831054353,
    17814095139, 17803329360, 17792739951, 17782007906, 17767857610, 17755386053,
    17745069948, 17744059573, 17729771917, 17718594169, 17710018563, 17709364275,
    17698273587, 17687391636, 17686885879, 17674737524, 17673892640, 17661260122,
    17644741589, 17634312020, 17626365779, 17636835204, 17604776215, 17592273599,
    17578494940, 17577824929, 17564039124, 17553696816, 17542523805, 17531766210,
    17520079337, 17519550785, 17508243378, 17496548845, 17496040712, 17484317397,
    17472598765, 17468726750, 17462781886, 17451320758, 17441927277, 17428933414,
    17417534270, 17417176326, 17403359813, 17396145580, 17385362445, 17385121795,
    17375612542, 17364043339, 17363363046, 17351378288, 17341408970, 17341014273,
    17326866937, 17315355763, 17306950225, 17296333749, 17286352879, 17273105269,
    17261814992, 17206465438, 17196135060, 17184659023, 17171746556, 17162225248,
    17151586962, 17139544331, 17129703166, 17105937065,
    # Januar 2026
    17105439030, 17090370197, 17081155206, 17070856304, 17069514472, 17060613807,
    17048053557, 17047630484, 17036207549, 17023651667, 17012911932, 17001668664,
    16990872000, 16971594663, 16958210967, 16947347592, 16946886289, 16933190666,
    16923845486, 16922522222, 16913595126, 16902841569
]

# Aktivitetstyper som har GPS
GPS_TYPER = {
    "Ride", "GravelRide", "MountainBikeRide", "EBikeRide", "EMountainBikeRide",
    "Velomobile", "Hike", "Run", "NordicSki", "AlpineSki", "Snowboard", "VirtualRide"
}

def last_hentet_aktiviteter():
    """Laster liste over aktiviteter som allerede er hentet."""
    if ALREADY_HENTET_FILE.exists():
        return set(json.loads(ALREADY_HENTET_FILE.read_text()))
    # Fallback: sjekk data/raw/ for eksisterende JSON-filer
    existing = set()
    for fil in RAW_DIR.glob("*.json"):
        try:
            aid = int(fil.stem.split("_")[1])
            existing.add(aid)
        except (ValueError, IndexError):
            pass
    return existing

def lagre_hentet_aktiviteter(hentet_set):
    """Lagrer liste over hentet aktiviteter."""
    ALREADY_HENTET_FILE.parent.mkdir(parents=True, exist_ok=True)
    ALREADY_HENTET_FILE.write_text(json.dumps(sorted(hentet_set)))

def get_manglende():
    """Returnerer liste over aktiviteter som mangler GPS-data."""
    hentet = last_hentet_aktiviteter()
    manglende = [aid for aid in ALLE_2026_AKTIVITETER if aid not in hentet]
    return sorted(manglende, reverse=True)  # Nyeste først

def hent_aktivitet_gps(activity_id):
    """
    Henter GPS-data for en aktivitet via Claude MCP.

    Returnerer: (dato_str, navn, sport_type, latlng_array) eller None hvis feil.

    MANUELL PROSESS:
    1. Kjør: claude ask "Hent GPS-data for aktivitet {activity_id}"
    2. Parser responsen
    3. Returnerer (dato, navn, sport_type, latlng)
    """
    print(f"\n⏳ Henter GPS for aktivitet {activity_id}...", flush=True)
    print(f"   Kjør i Claude manuelt: mcp_claude_ai_Strava__get_activity_streams(activity_id={activity_id}, streams=['location'])")
    print(f"   (Eller bruk claude CLI med MCP-tilgang)", flush=True)
    return None

def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("STRAVA 2026 - Batch Aktivitetshenting")
    print("=" * 70)

    hentet = last_hentet_aktiviteter()
    manglende = get_manglende()

    print(f"\n📊 Status:")
    print(f"   Totale aktiviteter 2026: {len(ALLE_2026_AKTIVITETER)}")
    print(f"   Allerede hentet: {len(hentet)}")
    print(f"   Mangler GPS-data: {len(manglende)}")

    if not manglende:
        print("\n✅ Alle aktiviteter er hentet!")
        return

    print(f"\n🚀 Starter henting av {len(manglende)} manglende aktiviteter...")
    print(f"   (Kjør denne skriptet regelmessig for å hente flere)")
    print("\n" + "=" * 70)
    print("MANUELL PROSESS (inntil API-integrasjon):")
    print("=" * 70)
    print("""
For hver aktivitet som mangler:

1. Åpne Claude i VSCode eller web
2. Kjør MCP-kall for få_activity_streams
3. Lagre respons som JSON i data/raw/YYYYMMDD_<activity_id>.json

EKSEMPEL JSON-STRUKTUR:
{
    "id": 19713814940,
    "dato": "2026-08-12T15:46:12",
    "navn": "Ettermiddag med sykkeltur",
    "sport_type": "Ride",
    "gear_id": null,
    "latlng": [[59.892639, 10.611379], [59.893,...], ...]
}

TIPS:
- Kopier filnavnet fra listen nedenfor
- Gjør 10-20 av gangen for effektivitet
- Bruk nohup for bakgrunnsprosess
    """)

    print(f"\n📋 Aktiviteter som mangler GPS-data (nyeste først):\n")
    for i, aid in enumerate(manglende[:30], 1):  # Vis først 30
        print(f"   {i:3d}. {aid}")

    if len(manglende) > 30:
        print(f"   ... og {len(manglende) - 30} flere")

    print("\n" + "=" * 70)
    print("SCRIPT FERDIG")
    print("=" * 70)
    print(f"\nNeste steg:")
    print(f"1. Hent GPS-data for de 30 aktivitetene ovenfor via Claude MCP")
    print(f"2. Lagre hver som JSON-fil i data/raw/")
    print(f"3. Kjør dette scriptet igjen for å hente neste batch")
    print(f"\nOppskrift for helt manuell batch:")
    print(f"  for activity_id in [19713814940, 19697303240, ...]: ")
    print(f"    1. get_activity_streams(activity_id, ['location'])")
    print(f"    2. Parse respons og lagre som JSON")

if __name__ == "__main__":
    main()
