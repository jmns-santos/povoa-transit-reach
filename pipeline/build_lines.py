#!/usr/bin/env python3
"""
Gera data/tp/lines.json — uma polilinha por percurso (route/shape) do GTFS
combinado, para a camada de contexto "Linhas de transporte público".

Quando a fonte tem shapes.txt (Metro, UNIR), a linha é a geometria real do
percurso. Quando não tem (Mov Cávado — a fonte original da AITC não inclui
shapes.txt), a linha é aproximada por segmentos retos entre as paragens, pela
ordem de uma viagem representativa de cada rota — fica marcada "approx": true
no ficheiro de saída, e o painel deve dizer isso ao utilizador.

Uso:
    python3 build_lines.py <pasta do GTFS combinado> [--out data/tp/lines.json]
"""
import argparse
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def read_rows(path, filename):
    fp = os.path.join(path, filename)
    if not os.path.exists(fp):
        return []
    with open(fp, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def op_of(prefixed_id):
    prefix = str(prefixed_id).split("_", 1)[0]
    return prefix if prefix in ("metro", "unir", "cavado") else "outro"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("gtfs", help="pasta do GTFS combinado (ex. data_src/gtfs_combined)")
    ap.add_argument("--out", default=os.path.join(HERE, "..", "data", "tp", "lines.json"))
    args = ap.parse_args()

    routes = {r["route_id"]: r for r in read_rows(args.gtfs, "routes.txt")}
    trips = read_rows(args.gtfs, "trips.txt")
    stops = {s["stop_id"]: s for s in read_rows(args.gtfs, "stops.txt")}

    shape_pts = {}
    for p in read_rows(args.gtfs, "shapes.txt"):
        shape_pts.setdefault(p["shape_id"], []).append(
            (int(p["shape_pt_sequence"]), float(p["shape_pt_lat"]), float(p["shape_pt_lon"]))
        )
    for sid in shape_pts:
        shape_pts[sid].sort(key=lambda t: t[0])
    print(f"{len(shape_pts)} shapes com geometria real (Metro/UNIR).")

    # uma viagem representativa por route_id, para rotas sem shape (Mov Cávado)
    rep_trip_by_route = {}
    for t in trips:
        rep_trip_by_route.setdefault(t["route_id"], t)

    st_by_trip = {}
    for row in read_rows(args.gtfs, "stop_times.txt"):
        st_by_trip.setdefault(row["trip_id"], []).append(row)
    for tid in st_by_trip:
        st_by_trip[tid].sort(key=lambda r: int(r["stop_sequence"]))

    lines, seen_shapes = [], set()
    for route_id, route in routes.items():
        op = op_of(route_id)
        name = route.get("route_short_name") or route.get("route_long_name") or route_id
        long_name = route.get("route_long_name") or ""
        route_trips = [t for t in trips if t["route_id"] == route_id]
        shape_ids = sorted({t["shape_id"] for t in route_trips if t.get("shape_id") in shape_pts})

        if shape_ids:
            for sid in shape_ids:
                if sid in seen_shapes:
                    continue
                seen_shapes.add(sid)
                coords = [[round(lat, 6), round(lon, 6)] for _, lat, lon in shape_pts[sid]]
                if len(coords) < 2:
                    continue
                lines.append({"route": name, "long_name": long_name, "op": op, "approx": False, "coords": coords})
        else:
            # sem shape nesta fonte (Mov Cávado): aproxima por paragem-a-paragem
            rt = rep_trip_by_route.get(route_id)
            if not rt:
                continue
            sts = st_by_trip.get(rt["trip_id"], [])
            coords = []
            for row in sts:
                s = stops.get(row["stop_id"])
                if s:
                    coords.append([round(float(s["stop_lat"]), 6), round(float(s["stop_lon"]), 6)])
            if len(coords) < 2:
                continue
            lines.append({"route": name, "long_name": long_name, "op": op, "approx": True, "coords": coords})

    out = {
        "note": "Linhas de transporte público: geometria real do percurso para o Metro do Porto e a UNIR "
                "(GTFS shapes.txt); para o Mov Cávado (a fonte da AITC não inclui shapes.txt) a linha é "
                "aproximada por segmentos retos entre as paragens de uma viagem representativa de cada rota "
                "(\"approx\": true).",
        "lines": lines,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    n_real = sum(1 for l in lines if not l["approx"])
    n_approx = sum(1 for l in lines if l["approx"])
    print(f"OK: {len(lines)} linhas ({n_real} com geometria real, {n_approx} aproximadas) -> {os.path.abspath(args.out)}")


if __name__ == "__main__":
    main()
