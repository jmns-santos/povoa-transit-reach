# Transit Reach — Póvoa de Varzim

**https://jmns-santos.github.io/povoa-transit-reach/**

Até onde se chega, a partir de um ponto e hora escolhidos, em transporte público ou de carro, na Póvoa de Varzim e Vila do Conde — e como compara um com o outro. Inspirado em [munich-transit-reach](https://github.com/ilyas-ku/munich-transit-reach) e [rhein-main-transit-reach](https://github.com/ilyas-ku/rhein-main-transit-reach), de `ilyas-ku`; `index.html` reaproveita o motor desses projetos (Connection Scan no browser + contornos d3), adaptado e traduzido para português de Portugal, com um segundo modo ("De carro") acrescentado.

Protótipo da Câmara Municipal da Póvoa de Varzim.

## Estado atual (2026-11-09)

| Camada | Estado | Fonte |
|---|---|---|
| Metro do Porto | **Real** | GTFS oficial da Metro do Porto |
| Autocarros (UNIR) | **Real**, filtrado à zona | GTFS oficial da UNIR, filtrado por coordenadas à Póvoa/Vila do Conde |
| Autocarros (Mov Cávado) | **Real**, filtrado à zona | GTFS oficial da AITC/Mov Cávado (linhas 106/107/111/120, Braga–Barcelos–Esposende–Viana do Castelo), filtrado por coordenadas |
| Fiabilidade (atrasos/cancelamentos) | **Não incluída** — mostra sempre o horário teórico | falta agregação histórica por paragem+linha+hora |
| Rede viária (carro e a pé) | **Real**, só concelho da Póvoa de Varzim (geometria e classificação); velocidades por tipo de via e atraso por cruzamento assumidos | shapefile da rede viária municipal |
| População em grelha | **Real** | BGRI 2021 (Censos), por subsecção estatística |
| Pontos de interesse | Opcional, script pronto, camada ligada por omissão | OpenStreetMap (Overpass) |
| Linhas de transporte público | **Real** (Metro, UNIR); **aproximada** (Mov Cávado, sem shapes.txt na fonte) | GTFS `shapes.txt` |
| Simulação em tempo real | Simulada a partir do horário (não é GTFS-RT) | horário real do dia de referência |

Área de estudo: concelho da Póvoa de Varzim (7 freguesias) + Vila do Conde. A rede viária (modos "De carro" e "A pé") é a rede municipal da Póvoa de Varzim — não inclui Vila do Conde, que é outro concelho com rede própria; por isso esses dois modos não alcançam Vila do Conde, mesmo estando dentro da moldura de estudo. O transporte público (Metro, UNIR, Mov Cávado) não tem esta limitação.

Tudo ficheiro estático (`data/tp/*.json`, `data/road/graph.json`) gerado pelo pipeline e servido pelo GitHub Pages — a página nunca acede a nenhuma base de dados ao vivo.

## Como usar

Abrir `index.html` (ou a página publicada). Quatro modos no painel à esquerda:
- **Transporte público** — Connection Scan sobre o horário combinado (Metro + UNIR + Mov Cávado, todos reais), horário teórico (ver "Fiabilidade" na tabela acima).
- **De carro** — Dijkstra sobre a rede viária municipal real, só nas vias com acesso automóvel, a velocidades assumidas por tipo de via.
- **A pé** — Dijkstra sobre a mesma rede real, incluindo passeios, ciclovias e atalhos só pedonais que o carro não pode usar; exclui auto-estradas.
- **Comparar** — transporte público e carro sobrepostos no mesmo mapa (TP a verde-água, carro a laranja).

Clicar no mapa ou arrastar o marcador branco muda o ponto de partida; a pesquisa usa o Nominatim (OpenStreetMap), limitado à caixa da Póvoa/Vila do Conde. O botão 📍 usa a localização do browser (pede autorização) como ponto de partida.

**Chegar a um destino.** O segundo campo de pesquisa ("Chegar a") aceita uma morada/local ou coordenadas `lat, lon`, e mostra o tempo estimado de chegada a esse ponto a partir da partida escolhida, no(s) modo(s) ativo(s).

**Camadas de contexto** — painel flutuante sobre o mapa, canto superior direito ("Camadas de contexto ▾"), não no painel esquerdo:
- **Pontos de interesse** (praias, património, alojamento, restauração, saúde, educação, multibancos, aeroportos, serviços públicos, lazer, comércio) — via OpenStreetMap, ligada por omissão; só aparece se `data/poi/poi.json` existir (ver `pipeline/importar_poi_osm.py`).
- **Paragens de transporte público** — sempre visíveis (sem interruptor, de propósito). Passar o cursor (ou tocar, em ecrã tátil) mostra o nome, a operadora e as próximas passagens por linha — com destino e hora — a partir da hora simulada abaixo.
- **Linhas de transporte público** — uma polilinha por percurso; geometria real para o Metro e a UNIR (têm `shapes.txt`), aproximada por segmentos retos entre paragens para o Mov Cávado (a fonte da AITC não inclui `shapes.txt`). Cada linha tem um tom de cor próprio dentro da família de cor da sua operadora (Metro do Porto / UNIR / Mov Cávado).
- **Rede viária (troços reais)** — os troços do grafo routável de carro/a pé, para conferir visualmente que as isócronas seguem a rede.
- **Simulação em tempo real** — mostra onde cada veículo (Metro/UNIR/Cávado) devia estar, segundo o horário real do dia de referência, à hora simulada — por omissão a hora atual do dispositivo, mas ajustável: scrubber de tempo, play/pausa, acelerador (1×–1800×), botão "Agora" e rasto opcional do movimento de cada veículo. Ícones distinguem autocarro de metro. **Não são posições reais** (não há integração GTFS tempo-real nesta versão) — é uma simulação a partir do horário estático, e entre duas paragens a posição é interpolada em linha reta pelo tempo decorrido, não pela curva exata da via.

## Estrutura

```
index.html                      página única (mapa Leaflet, motor CSA + Dijkstra, tudo em JS puro)
data/
  tp/meta.json, tp/c/HH.json    dados de transporte público (por hora)
  tp/lines.json                 uma polilinha por percurso (camada "Linhas de transporte público")
  tp/live.json                  horário por viagem do dia de referência (camada "Simulação em tempo real")
  road/graph.json               grafo da rede viária (nós + arestas, carro e a pé)
pipeline/
  build_demo_gtfs.py            gera um GTFS sintético de reserva (só se não houver um GTFS real)
  filter_gtfs_bbox.py           filtra um GTFS grande (ex. UNIR, toda a AMP) às viagens perto da área de estudo (inclui shapes.txt)
  combine_gtfs.py                junta vários GTFS (ex. Metro + UNIR + Cávado, todos reais) num só, com prefixos (inclui shapes.txt)
  build_explore_povoa.py        lê o GTFS combinado → data/tp/meta.json, tp/c/*, tp/live.json
  build_lines.py                lê o GTFS combinado → data/tp/lines.json (linhas, reais ou aproximadas)
  build_road_real.py            lê a rede viária municipal real (shapefile) → data/road/graph.json
  build_road_demo.py            alternativa de reserva: grelha sintética (carro + a pé), só se não houver shapefile
  importar_censos2021.py        lê um ficheiro BGRI 2021 do INE e preenche a população em data/tp/meta.json
  importar_poi_osm.py           descarrega pontos de interesse do OpenStreetMap (Overpass) → data/poi/poi.json
data_src/                       GTFS brutos usados para gerar data/ (não precisam de ir para o site publicado)
```

## Recriar os dados

```bash
cd pipeline
# 1. filtrar o GTFS da UNIR (toda a AMP) à zona de estudo, por coordenadas (não por nome)
python3 filter_gtfs_bbox.py <pasta ou .zip do GTFS da UNIR> ../data_src/gtfs_unir_filtrado \
    --box 41.18 -8.94 41.59 -8.53

# 1b. filtrar o GTFS do Mov Cávado (AITC) à mesma zona
python3 filter_gtfs_bbox.py <pasta ou .zip do GTFS do Mov Cávado> ../data_src/gtfs_cavado_filtrado \
    --box 41.18 -8.94 41.59 -8.53

# 2. combinar Metro + UNIR + Mov Cávado, todos reais
python3 combine_gtfs.py --out ../data_src/gtfs_combined \
    unir=../data_src/gtfs_unir_filtrado metro=<pasta ou .zip do GTFS real do Metro> \
    cavado=../data_src/gtfs_cavado_filtrado

# 3. gerar os dados de transporte público, as linhas e a rede viária
python3 build_explore_povoa.py ../data_src/gtfs_combined --dia 20261020 --fonte real
python3 build_lines.py ../data_src/gtfs_combined
python3 build_road_real.py <shapefile .shp da rede viária municipal>
# (ou, só se não houver shapefile disponível: python3 build_road_demo.py)
```

`build_explore_povoa.py` regenera `data/tp/meta.json` do zero — apaga sempre o campo de população, por isso corre sempre `importar_censos2021.py` a seguir (ver abaixo).

`--dia` tem de estar dentro da validade do `calendar.txt` de todos os GTFS combinados (uma terça-feira normal, na interseção dos vários calendários).

### Preencher a população (Censos 2021)

```powershell
pip install geopandas pyogrio
python importar_censos2021.py "C:\caminho\para\BGRI2021_Porto.gpkg"
```

Fonte: INE (http://mapas.ine.pt/download/index2021.phtml), ficheiro do distrito do Porto. O script filtra ao concelho automaticamente e atualiza `data/tp/meta.json`.

### Pontos de interesse (OpenStreetMap)

```powershell
pip install requests
python importar_poi_osm.py
```

Gera `data/poi/poi.json` (praias, património, alojamento, restauração, saúde, educação, multibancos, aeroportos, serviços públicos, lazer, comércio). Pode voltar a correr-se de vez em quando para atualizar a camada. Este ambiente de desenvolvimento não consegue chegar à Overpass API (rede bloqueada) — o script tem de correr numa máquina com acesso normal à internet; o ficheiro gerado (`data/poi/poi.json`) é depois copiado para o projeto e publicado normalmente.

## Publicar

Site estático. GitHub Pages: Settings → Pages → Deploy from a branch → `main`, pasta raiz. Pode ser embebido num iframe (ex. noutra aplicação municipal), ao contrário do planeador do Metro do Porto.

## Fontes e licenças

- Metro do Porto: GTFS oficial (`agency.txt`: Metro do Porto, https://www.metrodoporto.pt).
- UNIR Mobilidade da Área Metropolitana do Porto: GTFS oficial (https://unirmobilidade.pt), filtrado à zona de estudo.
- AITC/Mov Cávado: GTFS oficial (https://aitc.cimcavado.pt), filtrado à zona de estudo.
- Mapa base: Esri (World Dark Gray Canvas + Reference), © Esri, HERE, Garmin, © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors.
- Geocodificação: Nominatim.
- Pontos de interesse: OpenStreetMap, © colaboradores do OpenStreetMap (ODbL) — camada opcional, via Overpass API (ver "Pontos de interesse" acima).
- Motor de mapa: [Leaflet](https://leafletjs.com/). Motor de isócronas inspirado em [munich-transit-reach](https://github.com/ilyas-ku/munich-transit-reach) / [rhein-main-transit-reach](https://github.com/ilyas-ku/rhein-main-transit-reach) (ilyas-ku).
