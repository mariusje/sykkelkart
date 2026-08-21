"""Aggregerer GPS-punkter fra Strava-aktiviteter til H3-celler.

Hver aktivitet bidrar med maks ett treff per celle, slik at opptellingen svarer
på "hvor mange turer har vært innom denne cellen" og ikke "hvor mange sekunder
sto jeg stille her".
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

import h3

ROT = Path(__file__).resolve().parent.parent
RAW_DIR = ROT / "data" / "raw"
AGG_DIR = ROT / "data" / "aggregated"


def les_aktiviteter(raw_dir: Path = RAW_DIR) -> list[dict]:
    """Leser alle aktivitets-JSON-filer, nyeste først.

    Hver aktivitet får feltet `_filnavn` (filnavnet uten .json, altså
    `dato_aktivitetsid`) slik at det kan brukes som visningsidentifikator,
    f.eks. i tooltip på kartet.
    """
    aktiviteter = []
    for fil in sorted(raw_dir.glob("*.json"), reverse=True):
        data = json.loads(fil.read_text(encoding="utf-8"))
        data["_filnavn"] = fil.stem
        aktiviteter.append(data)
    return aktiviteter


def aktivitet_celler(aktivitet: dict, resolution: int) -> set[str]:
    """Unike H3-celler aktiviteten er innom.

    Duplikater innenfor samme aktivitet fjernes av settet, så en lang pause på
    ett sted teller like mye som å passere forbi.
    """
    return {
        h3.latlng_to_cell(lat, lon, resolution)
        for lat, lon in aktivitet.get("latlng", [])
    }


def grupper_aktiviteter_per_celle(aktiviteter: list[dict], resolution: int) -> dict[str, dict]:
    """For hver H3-celle: antall aktiviteter, hvilke (nyeste først), og sentrum.

    Returnerer cell_id -> {"antall": N, "aktiviteter": [filnavn, ...], "sentrum": [lat, lon]},
    sortert på antall (mest brukte celler først). `aktiviteter`-listen bruker
    `_filnavn` (dato_aktivitetsid) og er sortert på dato synkende, uavhengig
    av rekkefølgen aktivitetene ble lest inn i. `sentrum` gjør det mulig for
    nettleseren å avgjøre om en celle er innenfor gjeldende kartutsnitt uten
    å måtte regne ut H3-geometri på klientsiden.
    """
    treff: dict[str, list[dict]] = defaultdict(list)
    for aktivitet in aktiviteter:
        for celle in aktivitet_celler(aktivitet, resolution):
            treff[celle].append({"dato": aktivitet["dato"], "filnavn": aktivitet["_filnavn"]})

    celler = {}
    for celle, liste in treff.items():
        liste.sort(key=lambda x: x["dato"], reverse=True)
        celler[celle] = {
            "antall": len(liste),
            "aktiviteter": [x["filnavn"] for x in liste],
            "sentrum": list(h3.cell_to_latlng(celle)),
        }

    return dict(sorted(celler.items(), key=lambda kv: kv[1]["antall"], reverse=True))


def sammenlign_aktiviteter(x: dict, y: dict, resolution: int) -> dict:
    """Sammenligner to aktiviteter på H3-celle-nivå.

    Brukes som verifikasjon av aggregeringen: to turer langs samme vei bør
    dele mange celler, mens to urelaterte turer bør dele få eller ingen.
    """
    celler_x = aktivitet_celler(x, resolution)
    celler_y = aktivitet_celler(y, resolution)
    delte = celler_x & celler_y

    return {
        "resolution": resolution,
        "x": {"id": x["id"], "navn": x["navn"], "dato": x["dato"], "antall_celler": len(celler_x)},
        "y": {"id": y["id"], "navn": y["navn"], "dato": y["dato"], "antall_celler": len(celler_y)},
        "antall_delte_celler": len(delte),
        "andel_av_x": round(len(delte) / len(celler_x), 3) if celler_x else 0.0,
        "andel_av_y": round(len(delte) / len(celler_y), 3) if celler_y else 0.0,
        "delte_celler": sorted(delte),
    }


def aggreger(resolution: int, raw_dir: Path = RAW_DIR, agg_dir: Path = AGG_DIR) -> Path:
    """Aggregerer alle aktiviteter og skriver resultatet til data/aggregated."""
    aktiviteter = les_aktiviteter(raw_dir)
    celler = grupper_aktiviteter_per_celle(aktiviteter, resolution)

    resultat = {
        "resolution": resolution,
        "kantlengde_m": round(h3.average_hexagon_edge_length(resolution, unit="m"), 1),
        "antall_aktiviteter": len(aktiviteter),
        "antall_celler": len(celler),
        "aktiviteter": [
            {
                "id": a["id"],
                "dato": a["dato"],
                "navn": a["navn"],
                "sport_type": a["sport_type"],
                "filnavn": a["_filnavn"],
            }
            for a in aktiviteter
        ],
        # Sortert på antall aktiviteter, så de mest brukte områdene ligger øverst.
        # Hver celle: {"antall": N, "aktiviteter": [dato_aktivitetsid, ...]} (nyeste først).
        "celler": celler,
    }

    agg_dir.mkdir(parents=True, exist_ok=True)
    ut_fil = agg_dir / f"h3_activity_counts_res{resolution}.json"
    ut_fil.write_text(json.dumps(resultat, ensure_ascii=False), encoding="utf-8")
    return ut_fil


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolution", type=int, default=10, help="H3-oppløsning (standard: 10)")
    args = parser.parse_args()

    ut_fil = aggreger(args.resolution)
    resultat = json.loads(ut_fil.read_text(encoding="utf-8"))
    print(
        f"{ut_fil.relative_to(ROT)}: {resultat['antall_celler']} celler "
        f"fra {resultat['antall_aktiviteter']} aktiviteter "
        f"(res {resultat['resolution']}, ~{resultat['kantlengde_m']} m kantlengde)"
    )


if __name__ == "__main__":
    main()
