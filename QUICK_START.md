# Quick Start: Hent Resten av 2026-Aktiviteter

**Status**: 41 av 197 aktiviteter hentet (21%) ✅

---

## 5-Minutters Oppsett

### 1️⃣ Se Status
```bash
python3 hent_manglende_aktiviteter.py
```

Output viser hvilke ~160 aktiviteter som mangler.

### 2️⃣ Åpne Claude & Hent Batch

**Velg en av disse metodene:**

#### Metode A: VSCode Claude Extension (EASIEST)
1. Åpne VSCode
2. Åpne **Claude Chat** (Cmd+Shift+P)
3. Kopier-lim denne koden:

```
Hent GPS-data og metadata for disse Strava-aktivitetene fra 2026 
(nyeste først). Gi responsen som JSON-array med feltene:
id, dato (ISO 8601), navn, sport_type, gear_id (null ok), 
latlng (array av [lat,lon]).

Aktiviteter:
19713814940, 19697303240, 19682861416, 19669732558, 19655049134,
19637281633, 19637192210, 19626485473, 19611068642, 19598092479

Format eksempel:
[
  {"id": 19713814940, "dato": "2026-08-12T15:46:12", "navn": "...",
   "sport_type": "Ride", "gear_id": null, "latlng": [[59.892, 10.611], ...]},
  ...
]
```

#### Metode B: claude.ai Web
1. Gå til https://claude.ai
2. Be om samme ting (kopier koden over)
3. Få JSON-respons

### 3️⃣ Lagre Aktivitetene

**Option A: Fra fil**
```bash
# Kopier JSON fra Claude
cat > /tmp/batch.json << 'EOF'
[{"id": 19713814940, ...}]
EOF

# Lagre alle
python3 lagre_batch_aktiviteter.py /tmp/batch.json
```

**Option B: Interaktiv**
```bash
python3 lagre_batch_aktiviteter.py --interactive
```

### 4️⃣ Verifiser & Gjenta

```bash
# Se ny status
python3 hent_manglende_aktiviteter.py

# Gjenta steg 2-4 til 197/197 er hentet ✅
```

---

## Eksempel Workflow

**Tid: ~15 minutter for 10 aktiviteter**

```bash
# 1. Se hva som mangler (1 min)
$ python3 hent_manglende_aktiviteter.py
   📊 Status:
      Totale aktiviteter 2026: 197
      Allerede hentet: 41
      Mangler GPS-data: 156
   
   📋 Aktiviteter som mangler GPS-data (nyeste først):
   1. 19713814940
   2. 19697303240
   ...

# 2. Åpne Claude i VSCode (1 min)
# Ctrl+Shift+P -> "Claude: Open Chat"

# 3. Hent 10 første (Claude kjører API-kall: 5 min)
# Kopier-lim aktivitets-ID-ene og prompt fra over

# 4. Få JSON-respons fra Claude (automatisk)
# Kopier responsene

# 5. Lagre (2 min)
$ python3 lagre_batch_aktiviteter.py /tmp/batch.json
   ✓ 20260812_19713814940.json (2842 GPS-punkter)
   ✓ 20260810_19697303240.json (1543 GPS-punkter)
   ...
   ✓ 10 aktiviteter lagret

# 6. Verifiser progresjon (1 min)
$ python3 hent_manglende_aktiviteter.py
   Totale aktiviteter 2026: 197
   Allerede hentet: 51  ← Gikk fra 41!
   Mangler GPS-data: 146

# 7. Gjenta steg 2-6 for neste batch 🔄
```

---

## Filer Du Skal Bruke

| Fil | Hva Den Gjør |
|-----|-------------|
| `hent_manglende_aktiviteter.py` | **Se status** - kjør for oversikt |
| `lagre_batch_aktiviteter.py` | **Lagre aktiviteter** - fra JSON |
| `HENTING_AKTIVITETER.md` | **Fullstendig guide** - detaljert prosess |
| `data/raw/` | **Hvor filene lagres** - JSON-filer |

---

## Format: JSON fra Claude

Claude skal returnere dette formatet:

```json
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
    "navn": "Morgen løpetur",
    "sport_type": "Run",
    "gear_id": null,
    "latlng": [[60.123, 10.456], ...]
  }
]
```

**Viktig**: `latlng` må ha minst 1 koordinat-par!

---

## Tips

### Raskere Tempo
- Hent 10-20 aktiviteter per Claude-kall
- Jobbing med interaktiv mode (`--interactive`) hvis GPS-data allerede lagret lokalt

### Batch-Prompt For Claude
Kopier denne direkte til Claude:

```
Hent følgende fra Strava API og gi som JSON-array.
For hver aktivitet, gi: id, dato (ISO 8601), navn, sport_type, 
gear_id, og latlng (full GPS array).

IDs (hent disse først):
[19713814940, 19697303240, 19682861416, 19669732558, 19655049134,
 19637281633, 19637192210, 19626485473, 19611068642, 19598092479]
```

### Hvis Claude-API Feiler
Hvis Strava API-kall feiler i Claude, prøv å dele de 10 aktivitetene i mindre batches (5 av gangen).

---

## Progress Tracking

**Målet**: 197/197 aktiviteter

Hver gang du kjører `python3 hent_manglende_aktiviteter.py`, du vil se:
- `Allerede hentet: X` skal øke
- `Mangler GPS-data: Y` skal minke

**Mål**: Fra 41 → 197 ✅

---

## Neste Steg Etter Ferdig

Når alle 197 er hentet:

```bash
# Oppdater kartet
python3 -m sykkelkart.h3_agg
python3 -m sykkelkart.kart_vis

# Åpne kartet
open maps/sykkelkart.html
```

---

## Spørsmål?

Se `HENTING_AKTIVITETER.md` for utfyllende guide.
