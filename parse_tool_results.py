#!/usr/bin/env python3
"""
Parse tool-results fra Claude & lagre JSON aktiviteter direkte.

BRUK:
  python3 parse_tool_results.py                  # Parse siste fil
  python3 parse_tool_results.py --list           # List alle tool-results
  python3 parse_tool_results.py --file "xyz.txt" # Parse spesifikk fil
"""

import json
import sys
import re
from pathlib import Path
from datetime import datetime

# Din Claude-project tool-results folder
TOOL_RESULTS_DIR = Path("/Users/mariusje/.claude/projects/-Users-mariusje-Projects-sykkelkart")

# Finn faktisk mappe (kan ha ulikt navn)
if not TOOL_RESULTS_DIR.exists():
    # Fallback: søk etter den
    possible = list(Path("/Users/mariusje/.claude/projects").glob("*sykkelkart*"))
    if possible:
        TOOL_RESULTS_DIR = possible[0]
    else:
        print("❌ Finner ikke .claude/projects-mappen")
        sys.exit(1)

# tool-results bør være inni der et sted
TOOL_RESULTS_PATHS = list(TOOL_RESULTS_DIR.rglob("tool-results"))
if TOOL_RESULTS_PATHS:
    TOOL_RESULTS_DIR = TOOL_RESULTS_PATHS[0]
else:
    TOOL_RESULTS_DIR = TOOL_RESULTS_DIR / "d3989493-f187-438b-ae58-1d74dc1f1f8b" / "tool-results"

RAW_DIR = Path("data/raw")
HENTET_FILE = Path("data/.aktiviteter_hentet.json")

def finn_siste_tool_results_fil():
    """Finner siste tool-results fil fra Claude."""
    if not TOOL_RESULTS_DIR.exists():
        print(f"❌ tool-results folder ikke funnet: {TOOL_RESULTS_DIR}")
        return None

    # Finn alle .txt filer
    filer = sorted(TOOL_RESULTS_DIR.glob("*.txt"), key=lambda x: x.stat().st_mtime, reverse=True)

    if not filer:
        print(f"❌ Ingen .txt filer i {TOOL_RESULTS_DIR}")
        return None

    return filer[0]

def list_tool_results():
    """List alle tool-results filer."""
    if not TOOL_RESULTS_DIR.exists():
        print(f"❌ Dir ikke funnet: {TOOL_RESULTS_DIR}")
        return

    filer = sorted(TOOL_RESULTS_DIR.glob("*.txt"), key=lambda x: x.stat().st_mtime, reverse=True)

    if not filer:
        print(f"Ingen filer i {TOOL_RESULTS_DIR}")
        return

    print(f"\n📂 Tool-results filer ({len(filer)} total):\n")
    for i, f in enumerate(filer[:20], 1):
        size_kb = f.stat().st_size / 1024
        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"   {i:2d}. {f.name:40s} ({size_kb:6.1f} KB) {mtime}")

    if len(filer) > 20:
        print(f"   ... og {len(filer) - 20} flere")

    print(f"\nSiste fil: {filer[0].name}")

def parse_tool_results_fil(filepath):
    """Parser JSON fra tool-results fil."""
    if not filepath.exists():
        print(f"❌ Fil ikke funnet: {filepath}")
        return None

    print(f"📄 Leser: {filepath.name}")

    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception as e:
        print(f"❌ Feil ved lesing: {e}")
        return None

    # Prøv å parse som JSON direkte
    try:
        data = json.loads(content)
        return data
    except json.JSONDecodeError:
        pass

    # Hvis det er en error med tool-results format, prøv å søke etter JSON
    # Claude lagrer ofte "[{...}]" innerst i responsen
    matches = re.findall(r'\[\s*{.*}\s*\]', content, re.DOTALL)
    if matches:
        try:
            data = json.loads(matches[-1])  # Ta siste match (mest sannsynlig korrekt)
            return data
        except json.JSONDecodeError:
            pass

    print(f"❌ Kunne ikke parse JSON fra {filepath.name}")
    print(f"   Første 500 tegn: {content[:500]}")
    return None

def lagre_aktiviteter(data):
    """Lagrer batch av aktiviteter."""
    if not isinstance(data, list):
        print(f"❌ Feil: Data må være liste, fikk {type(data)}")
        return 0

    if not data:
        print("⊘ Tom liste - ingenting å lagre")
        return 0

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    lagret = 0
    feil = 0

    print(f"\n📝 Lagrer {len(data)} aktiviteter...\n")

    for act in data:
        try:
            # Valider feltene
            required = ["id", "dato", "navn", "sport_type", "latlng"]
            missing = [k for k in required if k not in act]
            if missing:
                print(f"  ❌ ID {act.get('id', '???')}: Mangler {missing}")
                feil += 1
                continue

            # Sjekk at latlng har data
            if not act.get("latlng") or len(act["latlng"]) == 0:
                print(f"  ⊘ ID {act['id']}: Ingen GPS-data (hopper over)")
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
            print(f"  ❌ ID {act.get('id', '???')}: {e}")
            feil += 1

    print(f"\n{'='*60}")
    print(f"✓ {lagret} aktiviteter lagret")
    if feil > 0:
        print(f"❌ {feil} feil/hopper over")

    # Oppdater hentet-liste
    oppdater_hentet_liste()

    # Status
    total = len(list(RAW_DIR.glob("*.json")))
    print(f"Total aktiviteter i data/raw: {total}/197")

    return lagret

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

def main():
    print("=" * 60)
    print("🔍 Parse Tool-Results & Lagre Aktiviteter")
    print("=" * 60)

    # Håndter argumenter
    if "--list" in sys.argv:
        list_tool_results()
        return

    if "--file" in sys.argv:
        idx = sys.argv.index("--file")
        if idx + 1 < len(sys.argv):
            filename = sys.argv[idx + 1]
            filepath = TOOL_RESULTS_DIR / filename
            data = parse_tool_results_fil(filepath)
            if data:
                lagre_aktiviteter(data)
        return

    # Default: finn siste fil
    print(f"\n🔍 Søker etter siste tool-results fil...")
    print(f"   Mappe: {TOOL_RESULTS_DIR}\n")

    fil = finn_siste_tool_results_fil()
    if not fil:
        print("\n❌ Ingen tool-results filer funnet!")
        print(f"\nProsjekt folder: {TOOL_RESULTS_DIR}")
        print("\nKjør: python3 parse_tool_results.py --list")
        print("   ... for å se alle filer")
        return

    print(f"📂 Siste fil: {fil.name}")
    print(f"   Størrelse: {fil.stat().st_size / 1024:.1f} KB")
    print(f"   Lagret: {datetime.fromtimestamp(fil.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")

    # Parse
    data = parse_tool_results_fil(fil)
    if data:
        lagre_aktiviteter(data)
    else:
        print("\n💡 Hvis Claude returnerte HTML/error, se siste 500 tegn ovenfor")
        print("   Prøv å kjør Claude-kallet på nytt")

if __name__ == "__main__":
    main()
