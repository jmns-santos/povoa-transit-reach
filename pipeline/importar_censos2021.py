#!/usr/bin/env python3
"""
Importa a população residente dos Censos 2021 (BGRI — Base Geográfica de
Referenciação de Informação, ao nível da subsecção estatística) e preenche
a grelha de população usada na secção "Pessoas alcançadas" do painel
(data/tp/meta.json, campo "pop").

Fonte dos dados (pública, sem autenticação, oficial do INE):
    http://mapas.ine.pt/download/index2021.phtml
Nessa página: escolher o distrito do Porto, descarregar o GeoPackage (.gpkg)
ou Shapefile do BGRI 2021 (resultados por edifícios/alojamentos/famílias/
residentes, por secção e subsecção estatística). Não há um link de ficheiro
único e estável — a página é de navegação, por isso descarrega-se à mão.

(Nota: a 2026-11-09 o portal mapas.ine.pt estava temporariamente em
manutenção, a redirecionar para autenticacao.ine.pt/manutencao.html —
tenta mais tarde se der o mesmo. Isto não impede correr este script depois,
assim que o ficheiro estiver na pasta.)

Uso (no PowerShell, depois de instalar as dependências):

    pip install geopandas pyogrio
    python importar_censos2021.py "C:\caminho\para\BGRI2021_Porto.gpkg"

O script:
  1. Lê o ficheiro (GeoPackage ou Shapefile; deteta a camada com geometria
     de polígono e um campo de código de concelho/freguesia).
  2. Filtra só o concelho da Póvoa de Varzim (código DICOFRE a começar por
     "1313" — os 4 primeiros dígitos identificam o concelho; os últimos 2
     mudam por freguesia/subsecção).
  3. Detecta a coluna de população residente total (procura por nomes como
     "N_INDIVIDUOS", "RESIDENTES", "POP_RESIDENTE" — se não encontrar com
     confiança, lista as colunas disponíveis e pede para indicares a certa
     com --coluna, em vez de adivinhar).
  4. Para cada subsecção, usa o centróide para decidir em que célula da
     grelha fina do projeto (a mesma BOX/DLAT/DLON do pipeline) cai a sua
     população, e soma.
  5. Atualiza o campo "pop" em data/tp/meta.json, codificado em base64 como
     o resto do pipeline (Uint16Array).
"""
import argparse
import base64
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
META_PATH = os.path.join(HERE, "..", "data", "tp", "meta.json")

DICOFRE_CONCELHO = "1313"  # Póvoa de Varzim

CANDIDATOS_COLUNA_POP = [
    "N_INDIVIDUOS_RESIDENT", "N_INDIVIDUOS", "RESIDENTES_N", "POP_RESIDENTE",
    "N_RESIDENT", "RESIDENTES", "POPULACAO_RESIDENTE", "POP21",
]
CANDIDATOS_COLUNA_DICOFRE = ["DICOFRE", "DTMNFR21", "DTMNFR", "DICOFRE21", "BGRI21", "BGRI"]


def b64(a):
    return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode()


def escolher_coluna(colunas, candidatos, rotulo):
    cols_lower = {c.lower(): c for c in colunas}
    for cand in candidatos:
        if cand.lower() in cols_lower:
            return cols_lower[cand.lower()]
    # tentativa por substring
    for c in colunas:
        for cand in candidatos:
            if cand.lower() in c.lower():
                return c
    print(f"\nNão consegui identificar com confiança a coluna de {rotulo}.")
    print("Colunas disponíveis no ficheiro:")
    for c in colunas:
        print(f"  - {c}")
    print(f"\nVolta a correr com --{'dicofre' if 'dicofre' in rotulo else 'coluna'} <nome_da_coluna_certa>")
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ficheiro", help="GeoPackage (.gpkg) ou Shapefile (.shp) do BGRI 2021, já descarregado do INE")
    ap.add_argument("--camada", help="nome da camada dentro do GeoPackage, se houver mais do que uma")
    ap.add_argument("--coluna", help="nome da coluna de população residente, se o script não a detetar sozinho")
    ap.add_argument("--dicofre", help="nome da coluna do código de concelho/freguesia (DICOFRE), se o script não a detetar sozinho")
    args = ap.parse_args()

    try:
        import geopandas as gpd
    except ImportError:
        print("Falta o geopandas. Corre primeiro: pip install geopandas pyogrio")
        sys.exit(1)

    if args.camada:
        gdf = gpd.read_file(args.ficheiro, layer=args.camada)
    else:
        try:
            gdf = gpd.read_file(args.ficheiro)
        except Exception as e:
            import fiona
            camadas = fiona.listlayers(args.ficheiro)
            print(f"O ficheiro tem várias camadas: {camadas}")
            print("Volta a correr com --camada <nome>")
            sys.exit(1)

    print(f"{len(gdf)} polígonos lidos de {args.ficheiro}")

    col_dicofre = args.dicofre or escolher_coluna(gdf.columns, CANDIDATOS_COLUNA_DICOFRE, "código de concelho (DICOFRE)")
    col_pop = args.coluna or escolher_coluna(gdf.columns, CANDIDATOS_COLUNA_POP, "população residente")
    print(f"A usar a coluna '{col_dicofre}' para o concelho e '{col_pop}' para a população.")

    gdf[col_dicofre] = gdf[col_dicofre].astype(str)
    gdf = gdf[gdf[col_dicofre].str.startswith(DICOFRE_CONCELHO)].copy()
    print(f"{len(gdf)} subsecções no concelho da Póvoa de Varzim (código {DICOFRE_CONCELHO}).")
    if len(gdf) == 0:
        print("Nenhuma subsecção encontrada — confirma o nome/formato da coluna de código com --dicofre.")
        sys.exit(1)

    if gdf.crs is None:
        print("Aviso: o ficheiro não indica o sistema de coordenadas (CRS); a assumir WGS84 (EPSG:4326).")
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    # lê a mesma BOX/DLAT/DLON usada no resto do pipeline, a partir do meta.json já gerado
    with open(META_PATH, encoding="utf-8") as f:
        meta = json.load(f)
    S, W, N, E = meta["box"]
    DLAT, DLON = meta["dlat"], meta["dlon"]
    ROWS, COLS = meta["rows"], meta["cols"]
    NCELL = ROWS * COLS

    pop = np.zeros(NCELL, dtype=np.float64)
    centroides = gdf.geometry.centroid
    fora = 0
    for geom, valor in zip(centroides, gdf[col_pop]):
        try:
            v = float(valor)
        except (TypeError, ValueError):
            continue
        lat, lon = geom.y, geom.x
        if not (S <= lat < N and W <= lon < E):
            fora += 1
            continue
        r = int((lat - S) / DLAT)
        c = int((lon - W) / DLON)
        pop[r * COLS + c] += v

    print(f"{fora} subsecções caem fora da caixa de estudo atual ({S},{W},{N},{E}) — normal se o concelho for maior que a caixa.")
    print(f"População total somada à grelha: {int(pop.sum())}")

    meta["pop"] = b64(pop.astype(np.uint16))
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, separators=(",", ":"))
    print(f"\nOK — {META_PATH} atualizado. Volta a publicar data/tp/meta.json (é o único ficheiro que muda).")


if __name__ == "__main__":
    main()
