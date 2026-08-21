"""Visualiserer H3-aggregerte sykkelaktiviteter som interaktivt folium-kart.

Kartet har en venstremeny hvor man kan filtrere hvilke aktiviteter som skal
telle med i fargeleggingen av H3-cellene: på sport type, på datointervall, og
aktivitet for aktivitet via en avkrysningstabell. All filtrering skjer i
nettleseren (JavaScript) etter at siden er lastet - selve HTML-filen er
fortsatt en frittstående, statisk fil uten noen server.
"""

import argparse
import json
from pathlib import Path

import folium
import h3
import numpy as np

ROT = Path(__file__).resolve().parent.parent
AGG_DIR = ROT / "data" / "aggregated"
KART_DIR = ROT / "maps"

# To celler regnes som del av samme geografiske klynge hvis avstanden mellom
# sentrene er innenfor denne grensen (transitivt, altså en kjede av nære
# celler holder sammen selv om klyngen totalt spenner over et større område).
KLYNGE_TERSKEL_KM = 20.0

SIDEMENY_BREDDE_PX = 380


def rgb_til_hex(r: int, g: int, b: int) -> str:
    """Konverterer RGB (0–255) til hex-farge."""
    return f"#{r:02x}{g:02x}{b:02x}"


def _haversine_km(lats: list[float], lons: list[float]) -> np.ndarray:
    """Parvis avstandsmatrise (km) mellom alle punkter, vektorisert."""
    R = 6371.0088
    lat_r = np.radians(np.asarray(lats))
    lon_r = np.radians(np.asarray(lons))
    dlat = lat_r[:, None] - lat_r[None, :]
    dlon = lon_r[:, None] - lon_r[None, :]
    a = np.sin(dlat / 2) ** 2 + np.cos(lat_r)[:, None] * np.cos(lat_r)[None, :] * np.sin(dlon / 2) ** 2
    return R * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def klynge_celler(celler: dict[str, dict], terskel_km: float = KLYNGE_TERSKEL_KM) -> list[dict]:
    """Grupperer H3-celler i geografisk sammenhengende klynger.

    Løser problemet med at aktiviteter fra f.eks. Norge og Italia tvinger
    kartet til å åpne på et zoomnivå der 76 m sekskanter er usynlige.
    Rutene i én region henger sammen via nære celler (single-linkage), mens
    store hull (typisk >100 km her) skiller regionene fra hverandre.

    Returnerer klynger sortert etter total aktivitetstreff, mest brukte først.
    """
    cell_ider = list(celler.keys())
    sentre = [h3.cell_to_latlng(c) for c in cell_ider]
    lats = [s[0] for s in sentre]
    lons = [s[1] for s in sentre]

    naboer = _haversine_km(lats, lons) <= terskel_km

    # Sammenhengskomponenter via BFS
    n = len(cell_ider)
    besøkt = [False] * n
    klynge_av = [-1] * n
    neste_klynge = 0
    for start in range(n):
        if besøkt[start]:
            continue
        kø = [start]
        besøkt[start] = True
        klynge_av[start] = neste_klynge
        while kø:
            i = kø.pop()
            for j in np.nonzero(naboer[i])[0]:
                j = int(j)
                if not besøkt[j]:
                    besøkt[j] = True
                    klynge_av[j] = neste_klynge
                    kø.append(j)
        neste_klynge += 1

    klynger: list[dict] = [{"celler": {}, "antall_treff": 0} for _ in range(neste_klynge)]
    for i, cell_id in enumerate(cell_ider):
        klynge = klynger[klynge_av[i]]
        klynge["celler"][cell_id] = celler[cell_id]
        klynge["antall_treff"] += celler[cell_id]["antall"]

    for klynge in klynger:
        grenser = [pt for cell_id in klynge["celler"] for pt in h3.cell_to_boundary(cell_id)]
        lats_k = [pt[0] for pt in grenser]
        lons_k = [pt[1] for pt in grenser]
        klynge["bounds"] = [[min(lats_k), min(lons_k)], [max(lats_k), max(lons_k)]]
        klynge["sentrum"] = (sum(lats_k) / len(lats_k), sum(lons_k) / len(lons_k))
        klynge["antall_celler"] = len(klynge["celler"])

    klynger.sort(key=lambda k: k["antall_treff"], reverse=True)
    return klynger


def aktiviteter_til_farge(antall: int, maks: int) -> tuple[str, float, float]:
    """Fargeleggingsfunksjon: gul → oransj → rød basert på aktivitetstall.

    Returnerer (hex_farge, fill_opacity, line_weight) der:
    - fill_opacity gjøres mindre gjennomskinnelig for svakt brukte områder
    - line_weight gjøres tykkere for sjelden brukte områder (synlig når zoomet ut)

    Den identiske fargelogikken finnes også i JavaScript (se JS_APP_MAL) siden
    fargelegging må kunne regnes på nytt i nettleseren når filtreringen endres.
    """
    # Normaliser til [0, 1]
    andel = min(1.0, antall / maks) if maks > 0 else 0.0

    if andel < 0.33:
        # Gul → Oransj
        t = andel / 0.33  # [0, 1] innen dette intervallet
        r = int(255)
        g = int(255 - t * 55)  # fra 255 til 200
        b = int(0)
        # Høyere baseline opasitet: sjeldne områder skal være synlige
        opasitet = 0.65 + t * 0.15  # fra 0.65 til 0.80
        # Tykkere linjer for sjeldne områder (synlig når zoomet langt ut)
        linjestyrke = 1.5 - t * 0.5  # fra 1.5 til 1.0
    elif andel < 0.66:
        # Oransj → Rød
        t = (andel - 0.33) / 0.33  # [0, 1] innen dette intervallet
        r = int(255)
        g = int(200 - t * 100)  # fra 200 til 100
        b = int(0)
        opasitet = 0.80 + t * 0.15  # fra 0.80 til 0.95
        linjestyrke = 1.0 - t * 0.3  # fra 1.0 til 0.7
    else:
        # Rød (mørk)
        t = (andel - 0.66) / 0.34  # [0, 1] innen dette intervallet
        r = int(255 - t * 50)  # fra 255 til 205 (litt mørkere rød)
        g = int(100 - t * 80)  # fra 100 til 20
        b = int(0)
        opasitet = 0.95  # Mørk rød skal være helt synlig
        linjestyrke = 0.7  # Tynnere linje for de hyppigst brukte

    return rgb_til_hex(r, g, b), min(1.0, opasitet), linjestyrke


# ---------------------------------------------------------------------------
# Sidemeny: HTML/CSS (statisk) og JavaScript-app (dynamisk filtrering)
# ---------------------------------------------------------------------------

SIDEMENY_CSS_MAL = """
<style>
#sidemeny {
    position: fixed;
    top: 0;
    left: 0;
    width: __BREDDE__px;
    height: 100vh;
    overflow-y: auto;
    background: #ffffff;
    border-right: 2px solid #ccc;
    z-index: 10000;
    font-family: -apple-system, Helvetica, Arial, sans-serif;
    font-size: 13px;
    box-sizing: border-box;
    padding: 12px;
}
#sidemeny h4 {
    margin: 14px 0 6px 0;
    font-size: 13px;
    text-transform: uppercase;
    color: #555;
    border-bottom: 1px solid #eee;
    padding-bottom: 3px;
}
#sidemeny-header {
    border-bottom: 2px solid #333;
    padding-bottom: 10px;
    margin-bottom: 4px;
}
#sidemeny-header b {
    font-size: 16px;
}
.filter-knapper {
    margin-bottom: 6px;
}
.filter-knapper button {
    font-size: 11px;
    padding: 3px 8px;
    margin-right: 6px;
    cursor: pointer;
    border: 1px solid #999;
    border-radius: 3px;
    background: #f5f5f5;
}
.filter-knapper button:hover {
    background: #e5e5e5;
}
#sport-liste {
    max-height: 220px;
    overflow-y: auto;
    border: 1px solid #eee;
    padding: 4px 6px;
}
.sport-rad {
    display: block;
    padding: 2px 0;
    cursor: pointer;
}
.sport-rad.grået {
    color: #aaa;
}
#dato-filter label {
    display: block;
    margin: 4px 0;
}
#dato-filter input[type="date"] {
    width: 100%;
    box-sizing: border-box;
    font-size: 12px;
}
#aktivitet-tabell {
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
}
#aktivitet-tabell th {
    text-align: left;
    position: sticky;
    top: 0;
    background: #fff;
    border-bottom: 1px solid #999;
    padding: 3px 4px;
}
#aktivitet-tabell td {
    padding: 3px 4px;
    border-bottom: 1px solid #f0f0f0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 110px;
}
#aktivitet-tabell tr.ekskludert {
    opacity: 0.4;
}
#aktivitet-tabell-wrapper {
    max-height: 420px;
    overflow-y: auto;
    border: 1px solid #eee;
}
#__MAP_ID__ {
    margin-left: __BREDDE__px !important;
    width: calc(100% - __BREDDE__px) !important;
}
</style>
"""

SIDEMENY_HTML_MAL = """
<div id="sidemeny">
    <div id="sidemeny-header">
        <b>Sykkelkart</b><br>
        <small>__ANTALL_AKTIVITETER__ aktiviteter, __ANTALL_CELLER__ H3-celler (res __RESOLUTION__)</small>
    </div>

    <h4>Sport type</h4>
    <div class="filter-knapper">
        <button id="btn-sport-velg-alle" type="button">Velg alle</button>
        <button id="btn-sport-velg-ingen" type="button">Velg ingen</button>
    </div>
    <div id="sport-liste"></div>

    <h4>Datointervall</h4>
    <div id="dato-filter">
        <label>Fra <input type="date" id="dato-fra"></label>
        <label>Til <input type="date" id="dato-til"></label>
    </div>

    <h4>Aktiviteter (<span id="aktivitet-antall">0 / 0</span>)</h4>
    <div id="aktivitet-tabell-wrapper">
        <table id="aktivitet-tabell">
            <thead>
                <tr><th></th><th>Dato</th><th>Navn</th><th>Sport</th><th>ID</th></tr>
            </thead>
            <tbody id="aktivitet-tabell-kropp"></tbody>
        </table>
    </div>
</div>
"""

# Placeholdere (__NAVN__) erstattes med .replace(), ikke f-string/.format(), for
# å slippe å escape alle {}-tegn som JavaScript-syntaksen er full av.
JS_APP_MAL = """
(function() {
    var AKTIVITETER = __AKTIVITETER_JSON__;
    var CELL_INFO = __CELL_INFO_JSON__;
    var AKTIVITET_MAP = {};
    AKTIVITETER.forEach(function(a) { AKTIVITET_MAP[a.filnavn] = a; });

    var valgteSportTyper = new Set(AKTIVITETER.map(function(a) { return a.sport_type; }));
    var datoFra = null;
    var datoTil = null;
    var manuelleTillegg = new Set();
    var manuelleUnntak = new Set();
    var KART = null;

    function alleSportTyper() {
        return Array.from(new Set(AKTIVITETER.map(function(a) { return a.sport_type; }))).sort();
    }

    function datoDel(iso) { return iso.slice(0, 10); }

    function globalDatoMinMaks() {
        var min = null, maks = null;
        for (var i = 0; i < AKTIVITETER.length; i++) {
            var d = datoDel(AKTIVITETER[i].dato);
            if (min === null || d < min) min = d;
            if (maks === null || d > maks) maks = d;
        }
        return [min, maks];
    }

    function aktiviteterIKartutsnitt() {
        if (!KART) {
            var alle = new Set();
            AKTIVITETER.forEach(function(a) { alle.add(a.filnavn); });
            return alle;
        }
        var bounds = KART.getBounds();
        var filnavn = new Set();
        for (var cellId in CELL_INFO) {
            var info = CELL_INFO[cellId];
            if (bounds.contains(L.latLng(info.sentrum[0], info.sentrum[1]))) {
                for (var i = 0; i < info.aktiviteter.length; i++) {
                    filnavn.add(info.aktiviteter[i]);
                }
            }
        }
        return filnavn;
    }

    // Kartutsnittet (nåværende panorering/zoom) er nå et primærfilter på lik
    // linje med sportstype og datointervall - en aktivitet som ikke er
    // synlig innenfor kartets grenser regnes ikke som inkludert, med mindre
    // den er manuelt lagt til.
    function passererFilter(akt, iViewportSett) {
        if (!iViewportSett.has(akt.filnavn)) return false;
        if (!valgteSportTyper.has(akt.sport_type)) return false;
        var d = datoDel(akt.dato);
        if (datoFra && d < datoFra) return false;
        if (datoTil && d > datoTil) return false;
        return true;
    }

    // Kilde til sannhet for hvilke aktiviteter som er "inkludert" akkurat nå:
    // kartutsnitt, sportstype og datofilteret, med manuelle av/på-valg fra
    // tabellen lagt oppå. De manuelle valgene nullstilles når sportstype
    // eller datointervall endres (se nullstillManuelleValg) - uten det ville
    // en aktivitet filtrene tilsier skal vises, kunne forbli skjult av et
    // gammelt, glemt avkrysningsvalg.
    function beregnInkludert() {
        var iViewportSett = aktiviteterIKartutsnitt();
        var inkludert = new Set();
        for (var i = 0; i < AKTIVITETER.length; i++) {
            var akt = AKTIVITETER[i];
            var passer = passererFilter(akt, iViewportSett);
            var inkl = (passer || manuelleTillegg.has(akt.filnavn)) && !manuelleUnntak.has(akt.filnavn);
            if (inkl) inkludert.add(akt.filnavn);
        }
        return inkludert;
    }

    function nullstillManuelleValg() {
        manuelleTillegg.clear();
        manuelleUnntak.clear();
    }

    function inkludertDatoMinMaks(inkludert) {
        var min = null, maks = null;
        inkludert.forEach(function(f) {
            var akt = AKTIVITET_MAP[f];
            if (!akt) return;
            var d = datoDel(akt.dato);
            if (min === null || d < min) min = d;
            if (maks === null || d > maks) maks = d;
        });
        return [min, maks];
    }

    // Datofeltene skal vise det faktiske intervallet blant det som er
    // inkludert akkurat nå (f.eks. étt fravalgt sted i tabellen, eller ett
    // kartutsnitt med bare én aktivitet), ikke stå fast på verdien som ble
    // satt ved sidelasting. De faktiske min/maks-grensene for feltene
    // (attributtene) røres ikke, så brukeren kan alltid utvide igjen.
    function oppdaterDatoRefleksjon(inkludert) {
        var minMaks = inkludertDatoMinMaks(inkludert);
        if (minMaks[0] === null) return;
        var fraInput = document.getElementById('dato-fra');
        var tilInput = document.getElementById('dato-til');
        if (fraInput) fraInput.value = minMaks[0];
        if (tilInput) tilInput.value = minMaks[1];
    }

    function beregnFiltrertPerCelle(inkludert) {
        var resultat = {};
        for (var cellId in CELL_INFO) {
            var kilde = CELL_INFO[cellId].aktiviteter;
            var filtrert = [];
            for (var i = 0; i < kilde.length; i++) {
                if (inkludert.has(kilde[i])) filtrert.push(kilde[i]);
            }
            resultat[cellId] = filtrert;
        }
        return resultat;
    }

    // Speiler aktiviteter_til_farge() i kart_vis.py.
    function fargeForAntall(antall, maks) {
        var andel = maks > 0 ? Math.min(1.0, antall / maks) : 0.0;
        var r, g, b, opasitet, linjestyrke, t;
        if (andel < 0.33) {
            t = andel / 0.33;
            r = 255; g = Math.round(255 - t * 55); b = 0;
            opasitet = 0.65 + t * 0.15;
            linjestyrke = 1.5 - t * 0.5;
        } else if (andel < 0.66) {
            t = (andel - 0.33) / 0.33;
            r = 255; g = Math.round(200 - t * 100); b = 0;
            opasitet = 0.80 + t * 0.15;
            linjestyrke = 1.0 - t * 0.3;
        } else {
            t = (andel - 0.66) / 0.34;
            r = Math.round(255 - t * 50); g = Math.round(100 - t * 80); b = 0;
            opasitet = 0.95;
            linjestyrke = 0.7;
        }
        var hex = '#' + [r, g, b].map(function(v) {
            var s = v.toString(16);
            return s.length === 1 ? '0' + s : s;
        }).join('');
        return [hex, Math.min(1.0, opasitet), linjestyrke];
    }

    function oppdaterKartLag(filtrertPerCelle) {
        if (!window.CELL_LAYERS) return;
        var maks = 0;
        for (var cellId in filtrertPerCelle) {
            if (filtrertPerCelle[cellId].length > maks) maks = filtrertPerCelle[cellId].length;
        }
        for (var lagId in window.CELL_LAYERS) {
            var layer = window.CELL_LAYERS[lagId];
            var filtrertListe = filtrertPerCelle[lagId] || [];
            if (filtrertListe.length === 0) {
                layer.setStyle({opacity: 0, fillOpacity: 0});
            } else {
                var res = fargeForAntall(filtrertListe.length, maks);
                layer.setStyle({color: res[0], fillColor: res[0], fillOpacity: res[1], weight: res[2], opacity: 1});
                if (layer.setTooltipContent) {
                    layer.setTooltipContent(
                        "<div style='max-height:220px; overflow-y:auto;'>" + filtrertListe.join('<br>') + '</div>'
                    );
                }
            }
        }
    }

    function byggBadgeHtml(antall) {
        return "<div style='background-color: #333; color: white; border-radius: 50%; " +
            "width: 32px; height: 32px; display: flex; align-items: center; " +
            "justify-content: center; font-size: 11px; font-weight: bold; " +
            "border: 2px solid white; box-shadow: 0 0 4px rgba(0,0,0,0.5); cursor: pointer;'>" +
            antall + "</div>";
    }

    // Klyngesirklene (antall H3-celler) skal vise det samme filtrerte
    // utvalget som kartet og tabellen, ikke det statiske totaltallet fra
    // generering - ellers ville f.eks. et klikkbart område fortsatt vise
    // "12 celler" selv om filtrene nå bare treffer 3 av dem. Sirkler som
    // treffer 0 fjernes helt fra kartet i stedet for å stå igjen og vise
    // "0" (typisk et område utenfor gjeldende kartutsnitt).
    function oppdaterKlyngeBadges(filtrertPerCelle) {
        if (!window.KLYNGE_MARKERS || !KART) return;
        window.KLYNGE_MARKERS.forEach(function(klynge) {
            var antallCellerMedTreff = 0;
            var aktiviteterSett = new Set();
            klynge.cellIds.forEach(function(cellId) {
                var filtrert = filtrertPerCelle[cellId] || [];
                if (filtrert.length > 0) antallCellerMedTreff++;
                filtrert.forEach(function(f) { aktiviteterSett.add(f); });
            });
            if (antallCellerMedTreff === 0) {
                if (KART.hasLayer(klynge.marker)) {
                    KART.removeLayer(klynge.marker);
                }
                return;
            }
            if (!KART.hasLayer(klynge.marker)) {
                klynge.marker.addTo(KART);
            }
            klynge.marker.setIcon(L.divIcon({html: byggBadgeHtml(antallCellerMedTreff)}));
            if (klynge.marker.setTooltipContent) {
                klynge.marker.setTooltipContent(
                    antallCellerMedTreff + ' celler, ' + aktiviteterSett.size + ' aktiviteter inkludert – klikk for å zoome hit'
                );
            }
        });
    }

    function tegnSportFilter() {
        var container = document.getElementById('sport-liste');
        if (!container) return;
        var iVisning = aktiviteterIKartutsnitt();
        var typerIVisning = new Set();
        iVisning.forEach(function(f) {
            var akt = AKTIVITET_MAP[f];
            if (akt) typerIVisning.add(akt.sport_type);
        });
        var alle = alleSportTyper();
        var topp = alle.filter(function(t) { return typerIVisning.has(t); });
        var bunn = alle.filter(function(t) { return !typerIVisning.has(t); });

        container.innerHTML = '';
        function lagRad(type, grået) {
            var rad = document.createElement('label');
            rad.className = grået ? 'sport-rad grået' : 'sport-rad';
            var boks = document.createElement('input');
            boks.type = 'checkbox';
            boks.checked = valgteSportTyper.has(type);
            boks.addEventListener('change', function() {
                if (boks.checked) { valgteSportTyper.add(type); } else { valgteSportTyper.delete(type); }
                nullstillManuelleValg();
                oppdaterAlt();
            });
            rad.appendChild(boks);
            rad.appendChild(document.createTextNode(' ' + type));
            container.appendChild(rad);
        }
        topp.forEach(function(t) { lagRad(t, false); });
        bunn.forEach(function(t) { lagRad(t, true); });
    }

    function tegnTabell(inkludert) {
        var tbody = document.getElementById('aktivitet-tabell-kropp');
        if (!tbody) return;
        var sortert = AKTIVITETER.slice().sort(function(a, b) {
            var aI = inkludert.has(a.filnavn), bI = inkludert.has(b.filnavn);
            if (aI !== bI) return aI ? -1 : 1;
            if (a.dato < b.dato) return 1;
            if (a.dato > b.dato) return -1;
            return 0;
        });
        tbody.innerHTML = '';
        sortert.forEach(function(akt) {
            var inkl = inkludert.has(akt.filnavn);
            var tr = document.createElement('tr');
            if (!inkl) tr.className = 'ekskludert';

            var tdBoks = document.createElement('td');
            var boks = document.createElement('input');
            boks.type = 'checkbox';
            boks.checked = inkl;
            boks.addEventListener('change', function() {
                if (boks.checked) {
                    manuelleTillegg.add(akt.filnavn);
                    manuelleUnntak.delete(akt.filnavn);
                } else {
                    manuelleUnntak.add(akt.filnavn);
                    manuelleTillegg.delete(akt.filnavn);
                }
                // Ingen nullstillManuelleValg() her - selve poenget med
                // avkrysningen er å sette en manuell overstyring.
                oppdaterAlt();
            });
            tdBoks.appendChild(boks);
            tr.appendChild(tdBoks);

            [datoDel(akt.dato), akt.navn, akt.sport_type, String(akt.id)].forEach(function(verdi) {
                var td = document.createElement('td');
                td.textContent = verdi;
                td.title = verdi;
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
        var teller = document.getElementById('aktivitet-antall');
        if (teller) teller.textContent = inkludert.size + ' / ' + AKTIVITETER.length;
    }

    // Én felles oppdateringsvei: uansett om endringen kom fra panorering/
    // zoom, sportstype-filteret, datointervallet eller en enkelt avkrysning
    // i tabellen, skal det samme "inkludert"-settet reflekteres i kartet,
    // klyngebadgene, datofeltene og tabellen samtidig.
    function oppdaterAlt() {
        var inkludert = beregnInkludert();
        var filtrertPerCelle = beregnFiltrertPerCelle(inkludert);
        oppdaterKartLag(filtrertPerCelle);
        oppdaterKlyngeBadges(filtrertPerCelle);
        tegnTabell(inkludert);
        oppdaterDatoRefleksjon(inkludert);
    }

    function settOppFilterUI() {
        var minMaks = globalDatoMinMaks();
        datoFra = minMaks[0];
        datoTil = minMaks[1];
        var fraInput = document.getElementById('dato-fra');
        var tilInput = document.getElementById('dato-til');
        if (fraInput) {
            fraInput.min = minMaks[0]; fraInput.max = minMaks[1]; fraInput.value = minMaks[0];
            fraInput.addEventListener('change', function() {
                datoFra = fraInput.value;
                nullstillManuelleValg();
                oppdaterAlt();
            });
        }
        if (tilInput) {
            tilInput.min = minMaks[0]; tilInput.max = minMaks[1]; tilInput.value = minMaks[1];
            tilInput.addEventListener('change', function() {
                datoTil = tilInput.value;
                nullstillManuelleValg();
                oppdaterAlt();
            });
        }
        var btnAlle = document.getElementById('btn-sport-velg-alle');
        var btnIngen = document.getElementById('btn-sport-velg-ingen');
        if (btnAlle) btnAlle.addEventListener('click', function() {
            valgteSportTyper = new Set(alleSportTyper());
            nullstillManuelleValg();
            tegnSportFilter();
            oppdaterAlt();
        });
        if (btnIngen) btnIngen.addEventListener('click', function() {
            valgteSportTyper = new Set();
            nullstillManuelleValg();
            tegnSportFilter();
            oppdaterAlt();
        });
    }

    window.addEventListener('load', function() {
        KART = __KART_VAR__;
        window.CELL_LAYERS = __CELL_LAYER_ASSIGNMENTS__;
        window.KLYNGE_MARKERS = __KLYNGE_MARKERS_JS__;

        // Sidemenyen tar plass fra kartet - uten dette blir tiles feilplassert
        // til brukeren pan/zoomer manuelt første gang.
        KART.invalidateSize();
        __REFIT_BOUNDS__

        settOppFilterUI();
        tegnSportFilter();
        oppdaterAlt();

        // Panorering/zoom endrer både hvilke sportstyper som regnes som "i
        // kartutsnittet" (filterlisten) OG selve det inkluderte settet
        // (kartutsnittet er nå et primærfilter, se beregnInkludert). De
        // manuelle avkrysningene i tabellen består likevel gjennom
        // panorering - bare sportstype/dato-endring nullstiller dem.
        KART.on('moveend', function() {
            tegnSportFilter();
            oppdaterAlt();
        });
    });
})();
"""


def tegn_kart(agg_fil: Path = AGG_DIR / "h3_activity_counts_res10.json") -> folium.Map:
    """Tegner interaktivt folium-kart av H3-celler.

    Retunerer det ferdige folium.Map-objektet slik at andre kan legge til ting,
    eller lagres direkte via .save().
    """
    data = json.loads(agg_fil.read_text(encoding="utf-8"))
    celler = data["celler"]  # dict av cell_id -> {"antall", "aktiviteter", "sentrum"}

    if not celler:
        raise ValueError("Ingen celler i aggregatet")

    maks_antall = max(info["antall"] for info in celler.values())

    # Grupper cellene geografisk. Uten dette ville f.eks. aktiviteter i Norge
    # og Italia tvunget kartet til å åpne på landsdel-nivå zoom, der 76 m
    # sekskanter er usynlige piksler.
    klynger = klynge_celler(celler)

    # Samle alle grensepunkter, for full-oversikt-visningen
    alle_latlng = []

    kart = folium.Map(
        location=[60.0, 11.0],  # midlertidig, fit_bounds justerer nedenfor
        zoom_start=5,
        tiles="OpenStreetMap",
    )

    # Registrerer cell_id -> polygonets JS-variabelnavn, slik at filtrerings-
    # scriptet kan style om cellene på nytt uten å tegne dem på nytt.
    lag_registrering: list[tuple[str, str]] = []

    # Registrerer hvilke celle-ID-er som hører til hver klynge, og klyngens
    # markør-variabelnavn, slik at badge-tallet kan regnes om til "antall
    # celler med treff i gjeldende filter" i stedet for å stå fast på det
    # statiske totaltallet fra generering.
    klynge_registrering: list[tuple[list[str], str]] = []

    # Tegn hver celle som polygon (alle klynger tegnes, bare startvisningen er begrenset)
    for celle_id, info in celler.items():
        antall = info["antall"]
        aktivitets_liste = info["aktiviteter"]  # dato_aktivitetsid, allerede sortert nyeste først

        # H3 grenser som liste av (lat, lon)
        grenser = h3.cell_to_boundary(celle_id)
        alle_latlng.extend(grenser)

        farge, opasitet, linjestyrke = aktiviteter_til_farge(antall, maks_antall)

        # Tooltip (mouseover) viser hvilke aktiviteter som har vært innom
        # cellen, nyeste først. Scrollbar for celler med mange treff (f.eks.
        # daglige pendlestrekk) så tooltipen ikke blir uleselig lang.
        # Oppdateres dynamisk av JS_APP_MAL når sidemeny-filtreringen endres.
        tooltip_html = (
            "<div style='max-height:220px; overflow-y:auto;'>"
            + "<br>".join(aktivitets_liste)
            + "</div>"
        )

        polygon = folium.Polygon(
            locations=grenser,
            color=farge,
            fill=True,
            fillColor=farge,
            fillOpacity=opasitet,
            weight=linjestyrke,
            popup=f"{celle_id}<br>{antall} aktiviteter totalt",
            tooltip=tooltip_html,
        )
        polygon.add_to(kart)
        lag_registrering.append((celle_id, polygon.get_name()))

    full_bounds = None
    if alle_latlng:
        lats = [pt[0] for pt in alle_latlng]
        lons = [pt[1] for pt in alle_latlng]
        full_bounds = [[min(lats), min(lons)], [max(lats), max(lons)]]

    # Start med å vise alle områdene samtidig
    if full_bounds is not None:
        kart.fit_bounds(bounds=full_bounds, padding=(0.05, 0.05))

    # Klikkbare markører for hvert område. Ved åpning er polygonene usynlige
    # smånyanser i denne oversikten, så markørene er det man faktisk ser og
    # kan navigere via – klikk zoomer inn på det valgte området.
    for klynge in klynger:
        lat, lon = klynge["sentrum"]
        badge_html = f"""
        <div style="background-color: #333; color: white; border-radius: 50%;
             width: 32px; height: 32px; display: flex; align-items: center;
             justify-content: center; font-size: 11px; font-weight: bold;
             border: 2px solid white; box-shadow: 0 0 4px rgba(0,0,0,0.5); cursor: pointer;">
        {klynge["antall_celler"]}
        </div>
        """
        markør = folium.Marker(
            location=[lat, lon],
            icon=folium.DivIcon(html=badge_html),
            tooltip=(
                f"{klynge['antall_celler']} celler, {klynge['antall_treff']} aktivitetstreff totalt "
                "– klikk for å zoome hit"
            ),
        )
        markør.add_to(kart)
        klynge_registrering.append((list(klynge["celler"].keys()), markør.get_name()))
        bounds_js = json.dumps(klynge["bounds"])
        # Utsatt til 'load': hele kartets script er én blokk der var-deklarasjoner
        # hoistes, så markør-variabelen finnes (men er undefined) før den faktiske
        # L.marker(...)-tildelingen lenger ned i samme script. Uten utsettelse
        # feiler .on(...) med "undefined is not an object".
        kart.get_root().script.add_child(
            folium.Element(
                f"window.addEventListener('load', function() {{ "
                f"{markør.get_name()}.on('click', function(e) {{ "
                f"{kart.get_name()}.fitBounds({bounds_js}); }}); }});"
            )
        )

    # Knapp for å zoome ut og se alle klynger samtidig
    if full_bounds is not None and len(klynger) > 1:
        full_bounds_js = json.dumps(full_bounds)
        vis_alt_html = f"""
        <div style="position: fixed; top: 10px; right: 10px; z-index:9999;">
        <button onclick='{kart.get_name()}.fitBounds({full_bounds_js});'
             style="background: white; border: 2px solid grey; border-radius: 4px;
             padding: 6px 10px; font-size: 12px; cursor: pointer;">
        Vis alle områder
        </button>
        </div>
        """
        kart.get_root().html.add_child(folium.Element(vis_alt_html))

    # Fargeforklaring
    fargelegende_html = """
    <div style="position: fixed; bottom: 50px; right: 10px; width: 180px;
         background-color: white; border:2px solid grey; z-index:9999;
         font-size:12px; padding: 10px;">
    <b>Aktivitetsfrekvens</b><br>
    <span style="color: yellow; font-weight: bold;">■</span> Sjelden brukt<br>
    <span style="color: orange; font-weight: bold;">■</span> Moderat<br>
    <span style="color: red; font-weight: bold;">■</span> Ofte brukt<br>
    <span style="color: darkred; font-weight: bold;">■</span> Meget ofte brukt
    </div>
    """
    kart.get_root().html.add_child(folium.Element(fargelegende_html))

    # --- Sidemeny: CSS + HTML + JS-app ---

    css = SIDEMENY_CSS_MAL.replace("__BREDDE__", str(SIDEMENY_BREDDE_PX)).replace(
        "__MAP_ID__", kart.get_name()
    )
    kart.get_root().html.add_child(folium.Element(css))

    sidemeny_html = (
        SIDEMENY_HTML_MAL.replace("__ANTALL_AKTIVITETER__", str(data["antall_aktiviteter"]))
        .replace("__ANTALL_CELLER__", str(data["antall_celler"]))
        .replace("__RESOLUTION__", str(data["resolution"]))
    )
    kart.get_root().html.add_child(folium.Element(sidemeny_html))

    aktiviteter_json = json.dumps(data["aktiviteter"], ensure_ascii=False, separators=(",", ":"))
    cell_info = {cid: {"sentrum": info["sentrum"], "aktiviteter": info["aktiviteter"]} for cid, info in celler.items()}
    cell_info_json = json.dumps(cell_info, ensure_ascii=False, separators=(",", ":"))
    cell_layer_js = "{" + ",".join(f"{json.dumps(cid)}:{varnavn}" for cid, varnavn in lag_registrering) + "}"
    klynge_markers_js = (
        "["
        + ",".join(
            f"{{cellIds:{json.dumps(cell_ids)},marker:{varnavn}}}" for cell_ids, varnavn in klynge_registrering
        )
        + "]"
    )

    refit_bounds_js = f"{kart.get_name()}.fitBounds({json.dumps(full_bounds)});" if full_bounds is not None else ""

    js_app = (
        JS_APP_MAL.replace("__AKTIVITETER_JSON__", aktiviteter_json)
        .replace("__CELL_INFO_JSON__", cell_info_json)
        .replace("__CELL_LAYER_ASSIGNMENTS__", cell_layer_js)
        .replace("__KLYNGE_MARKERS_JS__", klynge_markers_js)
        .replace("__KART_VAR__", kart.get_name())
        .replace("__REFIT_BOUNDS__", refit_bounds_js)
    )
    kart.get_root().script.add_child(folium.Element(js_app))

    return kart


def lagre_kart(
    agg_fil: Path = AGG_DIR / "h3_activity_counts_res10.json",
    ut_dir: Path = KART_DIR,
) -> Path:
    """Tegner og lagrer kartet som HTML."""
    kart = tegn_kart(agg_fil)
    ut_dir.mkdir(parents=True, exist_ok=True)
    ut_fil = ut_dir / "sykkelkart.html"
    kart.save(str(ut_fil))
    return ut_fil


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agg",
        type=Path,
        default=AGG_DIR / "h3_activity_counts_res10.json",
        help="Sti til aggregert H3-fil (standard: data/aggregated/h3_activity_counts_res10.json)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=KART_DIR,
        help="Utgangskatalog (standard: maps/)",
    )
    args = parser.parse_args()

    ut_fil = lagre_kart(args.agg, args.out)
    print(f"Kart lagret: {ut_fil.relative_to(ROT)}")


if __name__ == "__main__":
    main()
