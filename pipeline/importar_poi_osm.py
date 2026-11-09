#!/usr/bin/env python3
"""
Descarrega pontos de interesse (praias, património, alojamento, restauração,
saúde, educação, multibancos, aeroportos, serviços públicos, lazer, comércio)
do OpenStreetMap, via Overpass API, para a área de estudo do projeto, e gera
data/poi/poi.json.

OpenStreetMap é mantido continuamente pela comunidade (ao contrário de um
levantamento manual pontual) — por isso é a fonte certa para esta camada de
contexto: fica tão atualizada quanto o próprio OSM, sem precisar de voltar a
carregar nada à mão.

Pede nós, vias e relações (praias e parques são muitas vezes mapeados como
polígono, não como ponto) — para vias/relações usa o centro geométrico
(Overpass "out center").

Este ambiente de desenvolvimento não consegue chegar à Overpass API (rede
bloqueada); corre este script numa máquina com acesso normal à internet:

    pip install requests
    python importar_poi_osm.py
"""
import json
import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_explore_povoa import BOX  # mesma caixa de estudo do resto do projeto

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
UA = "transit-reach-povoa/1.0 (uso municipal, protótipo)"

# categoria -> pares (tag, valor) OSM; valor None = qualquer valor dessa tag
CATEGORIAS = {
    "praia": [("natural", "beach"), ("leisure", "beach_resort")],
    "patrimonio": [("historic", None), ("tourism", "attraction"), ("tourism", "museum"),
                   ("tourism", "artwork"), ("tourism", "information")],
    "alojamento": [("tourism", "hotel"), ("tourism", "guest_house"), ("tourism", "hostel"),
                   ("tourism", "camp_site"), ("tourism", "chalet")],
    "restauracao": [("amenity", "restaurant"), ("amenity", "cafe"), ("amenity", "bar"),
                     ("amenity", "fast_food")],
    "saude": [("amenity", "hospital"), ("amenity", "pharmacy"), ("amenity", "clinic"),
              ("amenity", "doctors")],
    "educacao": [("amenity", "school"), ("amenity", "kindergarten"), ("amenity", "college"),
                 ("amenity", "university")],
    "multibancos": [("amenity", "atm")],
    "aeroportos": [("aeroway", "aerodrome")],
    "servicos": [("amenity", "townhall"), ("amenity", "library"), ("amenity", "post_office"),
                 ("amenity", "bank"), ("amenity", "police"), ("amenity", "fire_station")],
    "lazer": [("leisure", "park"), ("leisure", "garden"), ("leisure", "nature_reserve"),
              ("leisure", "sports_centre"), ("leisure", "pitch"), ("tourism", "viewpoint"),
              ("tourism", "picnic_site")],
    "comercio": [("shop", "supermarket"), ("shop", "mall"), ("amenity", "marketplace"),
                 ("amenity", "fuel")],
}

LABELS = {
    "praia": "Praias", "patrimonio": "Património", "alojamento": "Alojamento",
    "restauracao": "Restauração", "saude": "Saúde", "educacao": "Educação",
    "multibancos": "Multibancos", "aeroportos": "Aeroportos", "servicos": "Serviços públicos",
    "lazer": "Lazer", "comercio": "Comércio e combustível",
}


def filtro_ql(tag, valor):
    return f'["{tag}"="{valor}"]' if valor else f'["{tag}"]'


def fetch_categoria(filtros, box):
    s, w, n, e = box
    bbox = f"{s},{w},{n},{e}"
    blocos = "".join(
        f'node{filtro_ql(tag, valor)}({bbox});way{filtro_ql(tag, valor)}({bbox});relation{filtro_ql(tag, valor)}({bbox});'
        for tag, valor in filtros
    )
    query = f"[out:json][timeout:90];({blocos});out center;"
    resp = requests.post(OVERPASS_URL, data={"data": query}, headers={"User-Agent": UA}, timeout=120)
    resp.raise_for_status()
    return resp.json().get("elements", [])


def coords_de(el):
    if "lat" in el and "lon" in el:
        return el["lat"], el["lon"]
    c = el.get("center")
    if c:
        return c["lat"], c["lon"]
    return None, None


def main():
    all_points = []
    seen_ids = set()
    for cat, filtros in CATEGORIAS.items():
        print(f"a pedir '{LABELS[cat]}'...")
        try:
            elems = fetch_categoria(filtros, BOX)
        except requests.RequestException as e:
            print(f"  falhou: {e}")
            continue
        n_novos = 0
        for el in elems:
            key = (el.get("type"), el.get("id"))
            if key in seen_ids:
                continue
            lat, lon = coords_de(el)
            if lat is None:
                continue
            seen_ids.add(key)
            tags = el.get("tags", {})
            nome = tags.get("name") or tags.get("name:pt") or LABELS[cat]
            all_points.append({"name": nome, "cat": cat, "lat": round(lat, 6), "lon": round(lon, 6)})
            n_novos += 1
        print(f"  {n_novos} pontos")
        time.sleep(1)  # cortesia para com o serviço público da Overpass

    out = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "OpenStreetMap, © colaboradores do OpenStreetMap (ODbL)",
        "labels": LABELS,
        "points": all_points,
    }
    out_dir = os.path.join(HERE, "..", "data", "poi")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "poi.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"\nOK: {len(all_points)} pontos de interesse em {os.path.abspath(out_path)}")


if __name__ == "__main__":
    main()
