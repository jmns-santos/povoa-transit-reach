#!/usr/bin/env python3
"""
Combina vários GTFS (pastas ou .zip) numa só pasta de saída, prefixando os
ids de cada fonte para evitar colisões entre feeds (ex. "metro_5746",
"unir_pov01"). Usado para juntar o GTFS real do Metro do Porto (cobre a
linha B até à Póvoa de Varzim / Vila do Conde) com o GTFS sintético da UNIR
(autocarros, ainda de demonstração).

Uso:
    python combine_gtfs.py --out <pasta_saida> <prefixo1>=<gtfs1> <prefixo2>=<gtfs2> ...
"""
import argparse
import csv
import io
import os
import sys
import zipfile

TABLES = {
    "stops.txt": "stop_id",
    "routes.txt": "route_id",
    "trips.txt": "trip_id",
    "calendar.txt": "service_id",
    "calendar_dates.txt": "service_id",
}
TRIP_REF_COLS = {"route_id": "routes.txt", "service_id": "calendar.txt"}
STOP_TIMES_REF = "trips.txt"


def open_table(src, filename):
    if os.path.isdir(src):
        path = os.path.join(src, filename)
        if not os.path.exists(path):
            return None
        return open(path, newline="", encoding="utf-8-sig")
    zf = zipfile.ZipFile(src)
    names = [n for n in zf.namelist() if n.endswith(filename)]
    if not names:
        return None
    return io.TextIOWrapper(zf.open(names[0]), encoding="utf-8-sig")


def read_rows(src, filename):
    f = open_table(src, filename)
    if f is None:
        return []
    with f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sources", nargs="+", help="prefixo=caminho (ex. metro=/tmp/metro_gtfs)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    combined = {name: [] for name in list(TABLES) + ["stop_times.txt"]}
    fieldnames = {}

    def add_fieldnames(table, rows):
        if not rows:
            return
        seen = fieldnames.setdefault(table, [])
        for k in rows[0].keys():
            if k not in seen:
                seen.append(k)

    for spec in args.sources:
        prefix, path = spec.split("=", 1)

        stops = read_rows(path, "stops.txt")
        for r in stops:
            r["stop_id"] = f"{prefix}_{r['stop_id']}"
        combined["stops.txt"] += stops
        add_fieldnames("stops.txt", stops)

        routes = read_rows(path, "routes.txt")
        for r in routes:
            r["route_id"] = f"{prefix}_{r['route_id']}"
        combined["routes.txt"] += routes
        add_fieldnames("routes.txt", routes)

        calendar = read_rows(path, "calendar.txt")
        for r in calendar:
            r["service_id"] = f"{prefix}_{r['service_id']}"
        combined["calendar.txt"] += calendar
        add_fieldnames("calendar.txt", calendar)

        caldates = read_rows(path, "calendar_dates.txt")
        for r in caldates:
            r["service_id"] = f"{prefix}_{r['service_id']}"
        combined["calendar_dates.txt"] += caldates
        add_fieldnames("calendar_dates.txt", caldates)

        trips = read_rows(path, "trips.txt")
        for r in trips:
            r["trip_id"] = f"{prefix}_{r['trip_id']}"
            r["route_id"] = f"{prefix}_{r['route_id']}"
            r["service_id"] = f"{prefix}_{r['service_id']}"
        combined["trips.txt"] += trips
        add_fieldnames("trips.txt", trips)

        sts = read_rows(path, "stop_times.txt")
        for r in sts:
            r["trip_id"] = f"{prefix}_{r['trip_id']}"
            r["stop_id"] = f"{prefix}_{r['stop_id']}"
        combined["stop_times.txt"] += sts
        add_fieldnames("stop_times.txt", sts)

        print(f"{prefix}: {len(stops)} paragens, {len(routes)} linhas, {len(trips)} viagens, {len(sts)} passagens")

    for table, rows in combined.items():
        if not rows:
            continue
        with open(os.path.join(args.out, table), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames[table], restval="")
            w.writeheader()
            w.writerows(rows)

    print(f"\nGTFS combinado em: {os.path.abspath(args.out)}")
    print(f"  total: {len(combined['stops.txt'])} paragens, {len(combined['trips.txt'])} viagens, "
          f"{len(combined['stop_times.txt'])} passagens")


if __name__ == "__main__":
    main()
