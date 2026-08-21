# ✅ Oppskrift: Hent & Lagre Strava-Aktiviteter

**Status Nå**: 41/197 hentet (21%) | 156 mangler | 6.3 MB data

---

## Problemet Med Forrige Oppskrift

❌ **Forrige versjon sa**:
- Hent data i Claude → Kopier til `/tmp/batch.json` → Kjør script

❌ **Problem**: 
- Manuell kopier-lim fra Claude
- Claude lagrer resultat i `tool-results/` automatisk
- Bruker må finne filnavnet selv
- Ikke automatisert

---

## ✅ Bedre Oppskrift (Denne Her)

**Hvordan det FAKTISK fungerer:**

1. Du skriver prompt i Claude
2. Claude kjører Strava API via MCP
3. Resultat lagres AUTO i: `/Users/mariusje/.claude/projects/-Users-mariusje-Projects-sykkelkart/.../tool-results/FILNAVN.txt`
4. **Du kjører et script som LESER denne filen direkte** ← Dette er KEY!
5. Script parser JSON og lagrer til `data/raw/`

---

## Steg-for-Steg Arbeidsflyt

### **Steg 1: Se Status**
```bash
python3 hent_manglende_aktiviteter.py
```

Output:
```
📊 Status:
   Totale aktiviteter: 197
   Allerede hentet: 41
   Mangler: 156

📋 Neste 30 som mangler:
   19713814940
   19697303240
   ...
```

---

### **Steg 2: Åpne Claude og Kjør API-Kall**

Åpne Claude (VSCode eller claude.ai) og kjør DENNE koden:

```
Jeg trenger å hente full metadata + GPS for disse Strava-aktivitetene fra 2026.

Kjør list_activities for å få metadata, deretter get_activity_streams for GPS.

Gi output som JSON-array med feltene:
- id: aktivitets-ID
- dato: start_local (ISO 8601)
- navn: activity name
- sport_type: type
- gear_id: gear_id (null ok)
- latlng: location array fra streams

Aktiviteter (fra nyeste):
19713814940, 19697303240, 19682861416, 19669732558, 19655049134,
19637281633, 19637192210, 19626485473, 19611068642, 19598092479,
19586027059, 19570391382, 19557235686, 19544529282, 19516067871

Output som JSON-array:
[
  {"id": ..., "dato": "2026-...", "navn": "...", "sport_type": "...",
   "gear_id": null, "latlng": [[lat, lon], ...]},
  ...
]
```

**Claude vil:**
- Kjøre MCP-kall automagisk
- Returnere JSON-array
- Lagre output i `tool-results/FILNAVN.txt` (auto)

---

### **Steg 3: Parse & Lagre (Automatic!)**

❌ **IKKE kopier-lim noe fra Claude!**

✅ **Kjør dette scriptet i stedet:**

```bash
python3 parse_tool_results.py
```

**Det scriptet vil:**
1. Finne siste tool-results fil(er)
2. Parse JSON
3. Lagre direkte til `data/raw/YYYYMMDD_<id>.json`
4. Rapportere hva som ble lagret

Output:
```
🔍 Parser tool-results filer...

✓ 20260812_19713814940.json (2842 GPS-punkter)
✓ 20260810_19697303240.json (1543 GPS-punkter)
✓ 20260808_19682861416.json (892 GPS-punkter)
...
✓ 15 aktiviteter lagret

Total aktiviteter nå: 56/197 ✓
```

---

### **Steg 4: Gjenta Inntil Ferdig**

```bash
# Sjekk status
python3 hent_manglende_aktiviteter.py

# Hvis fortsatt < 197:
# - Åpne Claude igjen
# - Kjør prompt med NESTE 15 aktiviteter
# - Kjør: python3 parse_tool_results.py
# - Gjenta
```

---

## Filer Du Skal Bruke

| Fil | Hva Den Gjør |
|-----|-------------|
| `hent_manglende_aktiviteter.py` | **Se status** - hvilke mangler |
| `parse_tool_results.py` | **Parse & lagre** - lesER fra tool-results/ AUTO |
| `data/raw/` | **Output folder** - der JSON lagres |

---

## Eksempel Fullstendig Sesjon

```bash
# Terminal 1: Se status
$ python3 hent_manglende_aktiviteter.py
   Allerede hentet: 41
   Mangler: 156
   Neste 15:
   19713814940, 19697303240, ...

# Terminal 2: Åpne Claude
# VSCode: Cmd+Shift+P → "Claude: Open Chat"
# Lim inn prompten fra Steg 2 ovenfor

# Claude kjører automatisk:
# - list_activities
# - get_activity_streams
# - Returnerer JSON
# - Lagrer i tool-results/xyz123.txt

# Terminal 1: Parse og lagre (AUTOMATISK!)
$ python3 parse_tool_results.py
   🔍 Finner siste tool-results fil...
   📄 Leser: /Users/mariusje/.claude/projects/.../tool-results/b2k6siqtw.txt
   
   ✓ 20260812_19713814940.json (2842 pts)
   ✓ 20260810_19697303240.json (1543 pts)
   ... (15 filer)
   
   ✅ 15 aktiviteter lagret
   Total: 56/197

# Gjenta: Tilbake til Claude med neste batch
```

---

## Prompt Template (Kopier-Lim)

Bruk denne i Claude hver gang:

```
Hent Strava-data for disse aktivitetene fra 2026.
Jeg trenger: id, dato (ISO 8601), navn, sport_type, gear_id, latlng (GPS).

Kjør:
1. list_activities for metadata
2. get_activity_streams for location data

Aktiviteter (fra nyeste):
19713814940, 19697303240, 19682861416, 19669732558, 19655049134,
19637281633, 19637192210, 19626485473, 19611068642, 19598092479,
19586027059, 19570391382, 19557235686, 19544529282, 19516067871

Output som JSON-array, inkluderer latlng-koordinater.
```

---

## Tips

### Optimalt Batch-Størrelse
- **Per Claude-sesjon**: 10-15 aktiviteter
- **Tid**: ~5-10 minutter for API-kall
- **Resultat**: 1 tool-results fil med all data

### Hvis Du Misser tool-results Filnavnet
Ikke noe problem! Scriptet finner **automatisk** siste fil(er):

```bash
python3 parse_tool_results.py --list   # Vis alle tool-results filer
python3 parse_tool_results.py --file "xyz123.txt"  # Parse spesifikk fil
```

### Avslutt Når Som Helst
Hvis Du stopper midt i en batch, ingen problem:
- Neste gang Du kjører `hent_manglende_aktiviteter.py`, den ser hvilke du allerede lagret
- Velg neste batch å hente

---

## Sjekkliste Hver Sesjon

- [ ] `python3 hent_manglende_aktiviteter.py` → se status
- [ ] Åpne Claude
- [ ] Kopier-lim prompt + neste 15 aktivitets-IDer
- [ ] Vent på resultat (Claude lagrer auto til tool-results/)
- [ ] `python3 parse_tool_results.py` → parse & lagre
- [ ] Gjenta til 197/197 ✓

---

## Når Alt Er Hentet (197/197)

```bash
# Oppdater kartet
python3 -m sykkelkart.h3_agg
python3 -m sykkelkart.kart_vis

# Åpne kartet
open maps/sykkelkart.html
```
