# Henting av Strava-aktiviteter

## Status (2026-08-13)

| År | Status |
|----|--------|
| **2026** | ✅ Komplett — 101 aktiviteter med GPS, verifisert uten duplikater/kollisjoner |
| **2025 og eldre** | Delvis (7 filer fra 2025 finnes fra tidligere økt). Ikke systematisk hentet ennå. |

`data/raw/` inneholder 108 JSON-filer totalt, ~636 000 GPS-punkter.

`WeightTraining` og `VirtualRide` (Zwift o.l.) er bevisst utelatt — sistnevnte har
spillverden-koordinater (Watopia, Richmond osv.) som ikke hører hjemme på et
virkelig sykkelkart.

---

## Hvordan dette faktisk fungerer

Det finnes **ingen frittstående Strava API-tilgang** i dette prosjektet (ingen
client_id/secret, ingen token). Den eneste veien til Strava-data er MCP-verktøyene
(`mcp__claude_ai_Strava__*`) som er tilgjengelige **inne i en Claude-samtale**.
Det betyr at henting må gjøres av Claude direkte i en økt — det finnes ikke noe
CLI-kommando eller script du kan kjøre selv som henter nye data uten Claude.

**Be Claude, i en vanlig samtale i dette prosjektet:**

> "Komplettér data/raw med GPS for alle sykkeltype-aktiviteter i 2024"

Claude vil da:
1. Paginere `list_activities` for å bygge fullstendig metadata for året
2. Sammenligne med filnavn som allerede finnes i `data/raw/`
3. Hente `get_activity_streams` for hver manglende aktivitet
4. Skrive JSON-filer direkte til `data/raw/YYYYMMDD_<id>.json`
5. Verifisere at ingen filer kolliderte eller ble avkuttet

Dette skjer i bakgrunnen av samtalen — du trenger ikke kopiere JSON manuelt
mellom steg.

### Viktig teknisk detalj: unngå avkutting og kollisjon

`get_activity_streams` returnerer noen ganger så mye data at svaret ikke får
plass i samtalen — da lagres det automatisk til en fil Claude leser fra i
stedet. Men **korte aktiviteter** (under terskelen) kommer tilbake som ren
tekst i samtalen, og hvis Claude da skal skrive dette til disk manuelt, er det
risiko for at teksten kuttes av eller blandes med en annen aktivitet hentet i
samme batch (dette skjedde faktisk under 2026-hentingen og ble oppdaget og
rettet via en sanity-sjekk).

**Løsningen som fungerte:** be alltid om alle 11 tilgjengelige strømmer
(`location, time, distance, altitude, heart_rate, cadence, velocity_smooth,
grade_smooth, moving, watts, temp`), ikke bare `location`. Det økte
svarstørrelsen nok til at praktisk talt alle aktiviteter — også korte —
tvinges over i fil-modus, som er trygg å lese programmatisk uten
avskrivingsrisiko.

Etter hver batch bør det kjøres en sanity-sjekk (duplikat-ID-er og
identiske startkoordinater på tvers av filer) — se `total_points` og
kollisjonssjekken i denne økten som mal.

### Rate limits

Strava/MCP-laget håndterte 30-40 kall i tett rekkefølge uten synlige
begrensninger i denne økten. Skulle det oppstå feil fra rate-limiting,
er anbefalingen å kjøre i batcher på ~10-15 med en kort pause, ikke alt
på én gang.

---

## Metadata-cache

`data/.metadata_cache_2026.json` inneholder full aktivitetsmetadata (id, navn,
dato, sport_type, gear_id) for alle 222 aktiviteter i 2026, hentet via
`list_activities`. Denne kan gjenbrukes for å raskt regne ut hvilke
GPS-egnede aktiviteter som mangler, uten å måtte paginere API-et på nytt.
Tilsvarende cache bør bygges per år etter hvert som eldre data hentes.

---

## Neste steg for tidligere år

Be Claude gjenta samme prosess for ønsket år, f.eks:

> "Gjør det samme for 2025"

Claude bygger da en tilsvarende `data/.metadata_cache_2025.json`, sammenligner
mot eksisterende `data/raw/2025*.json`, og henter resten.

---

## Etter henting: oppdater kartet

```bash
python3 -m sykkelkart.h3_agg
python3 -m sykkelkart.kart_vis
open maps/sykkelkart.html
```

---

## Historikk

Denne filen beskrev tidligere en manuell copy-paste-arbeidsflyt via
`hent_manglende_aktiviteter.py` og `lagre_batch_aktiviteter.py`. Den
arbeidsflyten er utdatert — den la opp til at du selv skulle kopiere JSON
mellom Claude og terminalen i flere steg. Faktisk henting skjer nå direkte
av Claude inne i samtalen, som beskrevet over. `QUICK_START.md` beskriver
samme utdaterte flyt og bør leses med samme forbehold.
