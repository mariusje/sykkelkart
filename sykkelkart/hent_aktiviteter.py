"""Hent 3 år med sykkelaktiviteter fra Strava, filtrer på latlng, lagre med gear_id.

Kjøres via: uv run python -m sykkelkart.hent_aktiviteter

Trenger Strava API-tilgang via MCP. Henter alle aktiviteter fra 3 år tilbake,
filtrerer på outdoor-sykkeltyper, henter latlng-strøm for hver, og lagrer
som JSON med id, dato, navn, sport_type, gear_id, latlng.
"""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

# Importeres fra MCP ved kjøring. Dette er en plasseholder for dokumentasjon.
# I praksis kjøres dette inne i Claude-grensesnittet med MCP-tilgang.

SYKKELTYPER = {
    "Ride",
    "GravelRide",
    "MountainBikeRide",
    "EBikeRide",
    "EMountainBikeRide",
    "Velomobile",
}

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Vis hva som ville blitt hentet uten å faktisk gjøre det.",
    )
    args = parser.parse_args()

    # Beregn dato 3 år tilbake
    nå = datetime.now()
    tre_år_tilbake = nå - timedelta(days=365 * 3)

    print(f"""
    Skal hente sykkelaktiviteter fra {tre_år_tilbake.date()} til {nå.date()}

    Prosess:
    1. Hent alle aktiviteter fra Strava API (med paginering, max 100 per request)
    2. Filtrerer på sykkeltyper: {", ".join(sorted(SYKKELTYPER))}
    3. For hver kandidat: hent latlng-strøm
    4. Lagrer bare de som har latlng-data
    5. Inkluderer: id, dato (start_local), navn, sport_type, gear_id, latlng
    6. Lagrer som YYYYMMDD_<activity_id>.json under {RAW_DIR}/

    Filformat eksempel:
    {{
        "id": 12345678,
        "dato": "2026-08-09T13:50:25",
        "navn": "Afternoon Ride",
        "sport_type": "Ride",
        "gear_id": "b12345678",
        "latlng": [[59.892639, 10.611379], ...]
    }}

    Merk: gear_id kan være null hvis ingen utstyr er tilordnet.

    Kjør dette fra Claude-grensesnittet med mcp-tilgang, eller gjør Strava-
    API-kallene manuelt og lagre resultatene.
    """)

    if args.dry_run:
        print("(dry-run modus – ingen data hentet)")
        return

    print(
        "For å faktisk hente data må du kjøre dette fra Claude-grensesnittet "
        "med MCP Strava-tilgang."
    )


if __name__ == "__main__":
    main()
