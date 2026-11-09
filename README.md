# Transit Reach — Póvoa de Varzim

Até onde se chega, a partir de um ponto e hora escolhidos, em transporte público ou de carro, na Póvoa de Varzim e Vila do Conde — e como compara um com o outro. Inspirado em [munich-transit-reach](https://github.com/ilyas-ku/munich-transit-reach) e [rhein-main-transit-reach](https://github.com/ilyas-ku/rhein-main-transit-reach), de `ilyas-ku`; `index.html` reaproveita o motor desses projetos (Connection Scan no browser + contornos d3), adaptado e traduzido para português de Portugal, com um segundo modo ("De carro") acrescentado.

Protótipo da Câmara Municipal da Póvoa de Varzim.

## Estado atual (2026-11-09)

| Camada | Estado | Fonte |
|---|---|---|
| Metro do Porto | **Real** | GTFS oficial da Metro do Porto |
| Autocarros (UNIR) | **Real**, filtrado à zona | GTFS estático oficial da UNIR — cobre toda a Área Metropolitana do Porto (12 067 paragens); filtrado às viagens que tocam a Póvoa/Vila do Conde e zona próxima antes de entrar no pipeline (ver nota abaixo) |
| Fiabilidade (atrasos/cancelamentos) | **Não incluída** (todos os níveis = horário) | a UNIR tem GTFS-RT em produção (posições de veículos), mas falta a agregação por paragem+linha+hora |
| Rede viária (carro e a pé) | **Sintética** (grelha + eixos rápidos inventados) | ver nota sobre a rede viária municipal abaixo — essa fonte também ainda não tem rede real carregada |
| População em grelha | **Não incluída** (secção escondida) | ver nota sobre o INE/Censos 2021 abaixo |

**Tudo é ficheiro estático** — `data/tp/*.json` e `data/road/graph.json` são gerados pelo pipeline e servidos tal e qual pelo GitHub Pages. A página nunca acede a nenhuma base de dados ao vivo, por segurança: só lê estes JSON.

**Nota sobre o filtro da UNIR.** O GTFS da UNIR cobre toda a AMP; a filtragem por nome de paragem (`grep "póvoa"`) dá falsos positivos — várias zonas da AMP têm localidades chamadas "Póvoa" sem ser a de Varzim. Por isso `filter_gtfs_bbox.py` filtra por **coordenadas** (viagens que tocam pelo menos uma paragem dentro de uma caixa alargada à volta da Póvoa/Vila do Conde), mantendo cada viagem completa — algumas linhas seguem para fora da caixa visível no mapa (ex. Barcelos, Esposende); isso é esperado e não é um erro.

**Nota sobre a rede viária municipal.** A fonte certa para uma rede viária real com velocidade e capacidade por troço ainda está, pelo que se sabe, só em fase de testes com uma rede sintética, nunca com dados reais de produção — a rede sintética desta ferramenta não é por isso uma limitação só dela.

**Nota sobre o Google Maps Platform.** Há uma chave de API do Google Maps Platform disponível, criada para testar a Air Quality API — não para routing. O crédito experimental de 300 $/90 dias já deve ter expirado; resta o limite gratuito mensal permanente por API. As APIs de rotas/distâncias (Directions, Distance Matrix) podiam, em teoria, calibrar ou validar pontualmente as velocidades da rede sintética — mas essa chamada teria de correr a partir de uma máquina com rede sem restrições (não é alcançável a partir deste pipeline de desenvolvimento), e sempre sem exceder o limite gratuito mensal nem fazer upgrade da conta.

**Nota sobre o INE/Censos 2021.** Existem, para já, só os scripts de ligação à API de séries por concelho/freguesia (população residente, etc.) — os códigos ainda estão por confirmar, e essa API não dá uma grelha fina de população. Para a secção "Pessoas alcançadas" seria preciso um ficheiro à parte com a grelha BGRI/subsecção estatística dos Censos 2021 (INE/Geoportal); assim que existir, basta preencher `meta["pop"]` em `build_explore_povoa.py`.

## Como usar

Abrir `index.html` (ou a página publicada). Quatro modos no painel à esquerda:
- **Transporte público** — Connection Scan sobre o horário combinado (Metro + UNIR, ambos reais), com o controlo de fiabilidade (ainda sem efeito real, ver tabela acima).
- **De carro** — Dijkstra sobre a rede viária sintética, a 22/65 km/h.
- **A pé** — Dijkstra sobre a mesma rede sintética, a 4,8 km/h (não distingue passeios nem atalhos só pedonais).
- **Comparar** — transporte público e carro sobrepostos no mesmo mapa (TP a verde-água, carro a laranja).

Clicar no mapa ou arrastar o marcador branco muda o ponto de partida; a pesquisa usa o Nominatim (OpenStreetMap), limitado à caixa da Póvoa/Vila do Conde.

## Estrutura

```
index.html                      página única (mapa Leaflet, motor CSA + Dijkstra, tudo em JS puro)
data/
  tp/meta.json, tp/c/HH.json    dados de transporte público (por hora)
  road/graph.json               grafo da rede viária (nós + arestas, carro e a pé)
pipeline/
  build_demo_gtfs.py            gera um GTFS sintético de reserva (só se não houver um GTFS real)
  filter_gtfs_bbox.py           filtra um GTFS grande (ex. UNIR, toda a AMP) às viagens perto da área de estudo
  combine_gtfs.py                junta vários GTFS (ex. Metro + UNIR, ambos reais) num só, com prefixos
  build_explore_povoa.py        lê o GTFS combinado → data/tp/*
  build_road_demo.py            gera a rede viária sintética (carro + a pé) → data/road/graph.json
data_src/                       GTFS brutos usados para gerar data/ (não precisam de ir para o site publicado)
```

## Recriar os dados

```bash
cd pipeline
# 1. filtrar o GTFS da UNIR (toda a AMP) à zona de estudo, por coordenadas (não por nome)
python3 filter_gtfs_bbox.py <pasta ou .zip do GTFS da UNIR> ../data_src/gtfs_unir_filtrado \
    --box 41.18 -8.94 41.59 -8.53

# 2. combinar com o Metro real
python3 combine_gtfs.py --out ../data_src/gtfs_combined \
    unir=../data_src/gtfs_unir_filtrado metro=<pasta ou .zip do GTFS real do Metro>

# 3. gerar os dados de transporte público e a rede viária
python3 build_explore_povoa.py ../data_src/gtfs_combined --dia 20261020 --fonte real
python3 build_road_demo.py
```

`--dia` tem de estar dentro do período coberto pelo `calendar.txt` de **todos** os GTFS combinados — por exemplo, o GTFS do Metro descarregado em 2026-09 só é válido até 2026-10-25, enquanto o da UNIR vai até 2027-08-31; ao atualizar qualquer um dos ficheiros, verificar o novo período de validade e ajustar `--dia` (uma terça-feira normal, dentro da interseção dos dois calendários).

## O que falta para ficar mais completo

1. **Fiabilidade real**: construir, a partir do histórico de GTFS-RT já em produção, uma agregação por paragem+linha+hora (mediana, p80/p90/p95, taxa de cancelamento) e passá-la a `build_explore_povoa.py --fiabilidade ficheiro.csv` (colunas: `route_id,stop_id,hour,delay_p50_s,delay_p90_s,cancel_rate` — ver a função `load_reliability` para o formato exato esperado).
2. **Rede viária real** (carro e a pé): ligar a uma rede viária municipal real com velocidade e capacidade por troço, assim que existirem dados reais carregados (hoje só testado com rede sintética, ver nota acima), ou a um extrato OSM da área (teria também a rede só-pedonal, que a rede viária não tem), e escrever um `build_road_<fonte>.py` que gere o mesmo `data/road/graph.json` (nós + arestas `edge_w`/`edge_w_walk` + `cell_node`) a partir daí.
3. **População em grelha**: obter a grelha BGRI/subsecção dos Censos 2021 do INE/Geoportal (não a API de séries por concelho, que não tem essa granularidade) ou Eurostat GEOSTAT, e preencher `meta["pop"]` em `build_explore_povoa.py` (hoje fica a zeros, o que esconde a secção "Pessoas alcançadas" no painel).
4. **Calibração pontual com o Google Maps Platform**: usar a Directions/Distance Matrix API para validar as velocidades sintéticas contra algumas rotas reais — a correr a partir de uma máquina com acesso de rede normal, e sem exceder o limite gratuito mensal.

Nada disto exige mudar o front-end: `index.html` já lê o formato final; só os pipelines em `pipeline/` precisam de outra fonte.

## Publicar

Site estático — qualquer alojamento serve. Para GitHub Pages: criar o repositório, `git push`, ativar Pages a servir a raiz do `main`. Uma página estática no GitHub Pages não define `X-Frame-Options`/`frame-ancestors`, por isso **pode ser embebida num iframe** (ex. um widget doutra aplicação municipal), ao contrário do planeador do Metro do Porto (bloqueado por CSP).

## Fontes e licenças

- Metro do Porto: GTFS oficial (`agency.txt`: Metro do Porto, https://www.metrodoporto.pt).
- UNIR Mobilidade da Área Metropolitana do Porto: GTFS oficial (https://unirmobilidade.pt), filtrado à zona de estudo.
- Mapa base: Esri (World Dark Gray Canvas + Reference), © Esri, HERE, Garmin, © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors.
- Geocodificação: Nominatim.
- Motor de mapa: [Leaflet](https://leafletjs.com/). Motor de isócronas inspirado em [munich-transit-reach](https://github.com/ilyas-ku/munich-transit-reach) / [rhein-main-transit-reach](https://github.com/ilyas-ku/rhein-main-transit-reach) (ilyas-ku).
