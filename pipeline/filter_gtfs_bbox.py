#!/usr/bin/env python3
"""
Filtra um GTFS grande (ex. a UNIR, com toda a Área Metropolitana do Porto)
para só as viagens (trips) que tocam pelo menos uma paragem dentro de uma
bounding box alargada — mantém a viagem completa (todas as suas paragens),
para não cortar rotas a meio.

Uso:
    python filter_gtfs_bbox.py <gtfs_in> <gtfs_out> --box S W N E
"""
import argparse
import csv
import io
import os
import zipfile


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


def write_rows(out_dir, filename, rows):
    if not rows:
        return
    with open(os.path.join(out_dir, filename), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gtfs_in")
    ap.add_argument("gtfs_out")
    ap.add_argument("--box", nargs=4, type=float, metavar=("S", "W", "N", "E"), required=True)
    args = ap.parse_args()
    S, W, N, E = args.box

    stops = read_rows(args.gtfs_in, "stops.txt")
    inside_ids = {s["stop_id"] for s in stops if S <= float(s["stop_lat"]) <= N and W <= float(s["stop_lon"]) <= E}
    print(f"{len(stops)} paragens no GTFS de origem, {len(inside_ids)} dentro da caixa de filtro")

    stop_times = read_rows(args.gtfs_in, "stop_times.txt")
    trips_touching = set()
    for st in stop_times:
        if st["stop_id"] in inside_ids:
            trips_touching.add(st["trip_id"])
    print(f"{len(trips_touching)} viagens tocam a caixa")

    kept_stop_times = [st for st in stop_times if st["trip_id"] in trips_touching]
    kept_stop_ids = {st["stop_id"] for st in kept_stop_times}
    kept_stops = [s for s in stops if s["stop_id"] in kept_stop_ids]

    trips = read_rows(args.gtfs_in, "trips.txt")
    kept_trips = [t for t in trips if t["trip_id"] in trips_touching]
    kept_route_ids = {t["route_id"] for t in kept_trips}
    kept_service_ids = {t["service_id"] for t in kept_trips}

    routes = read_rows(args.gtfs_in, "routes.txt")
    kept_routes = [r for r in routes if r["route_id"] in kept_route_ids]

    calendar = read_rows(args.gtfs_in, "calendar.txt")
    kept_calendar = [c for c in calendar if c["service_id"] in kept_service_ids]
    calendar_dates = read_rows(args.gtfs_in, "calendar_dates.txt")
    kept_caldates = [c for c in calendar_dates if c["service_id"] in kept_service_ids]

    os.makedirs(args.gtfs_out, exist_ok=True)
    write_rows(args.gtfs_out, "stops.txt", kept_stops)
    write_rows(args.gtfs_out, "routes.txt", kept_routes)
    write_rows(args.gtfs_out, "trips.txt", kept_trips)
    write_rows(args.gtfs_out, "stop_times.txt", kept_stop_times)
    write_rows(args.gtfs_out, "calendar.txt", kept_calendar)
    write_rows(args.gtfs_out, "calendar_dates.txt", kept_caldates)

    print(f"Saída: {len(kept_stops)} paragens, {len(kept_routes)} linhas, {len(kept_trips)} viagens, "
          f"{len(kept_stop_times)} passagens -> {os.path.abspath(args.gtfs_out)}")


if __name__ == "__main__":
    main()
