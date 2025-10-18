<h1>🧠 API Data Extractor (Async)</h1>
<p>Ferramenta genérica e extensível para <strong>extração massiva de dados de APIs</strong> (com suporte a paginação, rate-limit, retries e salvamento em CSV/Parquet/Postgres).<br>
O projeto é assíncrono e inclui presets para a <strong>API de Tênis</strong> (<code>api.api-tennis.com</code>).</p>

<hr>

<h2>⚙️ Funcionalidades</h2>
<ul>
  <li>🔄 Requisições <strong>assíncronas</strong> com <code>aiohttp</code></li>
  <li>🕓 <strong>Rate-limit</strong> e <strong>concorrência</strong> configuráveis</li>
  <li>💥 <strong>Retries automáticos</strong> com backoff exponencial</li>
  <li>📄 Modos:
    <ul>
      <li><code>single</code> — chamadas diretas (ex.: <code>get_players?player_key=...</code>)</li>
      <li><code>page</code> — paginação <em>page/limit</em></li>
      <li><code>cursor</code> — paginação por cursor/token (<em>cursor/next</em>)</li>
      <li><code>players_harvest</code> — varredura de jogadores (torneios → fixtures → players)</li>
      <li><code>odds_harvest</code> — varredura de odds por fixture</li>
    </ul>
  </li>
  <li>📊 Normalização JSON → DataFrame (<code>pandas.json_normalize</code>)</li>
  <li>💾 <strong>Parquet</strong> (com fallback automático para <strong>CSV</strong>)</li>
  <li>🗄️ Postgres opcional via <code>SQLAlchemy</code></li>
  <li>🧩 <code>state.json</code> para incremental/cobertura</li>
  <li>🧠 Logs ricos com métricas de cobertura</li>
</ul>

<hr>

<h2>🧰 Estrutura do Projeto</h2>
<pre><code>Api-data-extractor/
├── src/
│   ├── __init__.py
│   ├── async_client.py      # HTTP assíncrono (aiohttp)
│   ├── config.py            # Carrega .env → AppConfig
│   ├── extractor.py         # Padrões de paginação (sync)
│   ├── logger.py            # Logging central
│   ├── normalizer.py        # JSON → tabela
│   ├── storage.py           # CSV/Parquet/Postgres
│   ├── incremental.py       # state.json (incremental)
│   ├── run_async.py         # Runner principal (async)
│   └── run_sync.py          # Runner síncrono (debug)
│
├── .env
├── requirements.txt
└── README.md
</code></pre>

<hr>

<h2>💽 Instalação</h2>
<pre><code># 1) Clonar
git clone https://github.com/seuuser/api-data-extractor.git
cd api-data-extractor

# 2) Venv (Windows com Python 3.13)
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3) Dependências
pip install -r requirements.txt
# (opcional, para Parquet)
pip install pyarrow
</code></pre>
<p><strong>Nota:</strong> Em Python 3.14, use <code>OUTPUT_FORMAT=csv</code> (pyarrow pode não ter wheel).</p>

<hr>

<h2>⚙️ Exemplos de <code>.env</code></h2>

<h3>🔹 Básico (modo <code>single</code>)</h3>
<pre><code>API_BASE_URL=https://api.api-tennis.com/tennis
API_KEY=SEU_API_KEY_AQUI
API_AUTH_TYPE=api_key
ENDPOINT_PATH=/
ITEM_KEY=result

PAGINATION_MODE=single
TENNIS_METHOD=get_players
TENNIS_PLAYER_KEY=137

OUTPUT_FORMAT=csv
OUTPUT_DIR=./data
RATE_LIMIT_PER_MINUTE=60
CONCURRENCY=5
REQUEST_TIMEOUT_SEC=30
LOG_LEVEL=INFO
</code></pre>

<h3>🔹 Varredura de jogadores (<code>players_harvest</code>)</h3>
<pre><code>API_BASE_URL=https://api.api-tennis.com/tennis
API_KEY=SEU_API_KEY_AQUI
ENDPOINT_PATH=/
ITEM_KEY=result

PAGINATION_MODE=players_harvest
TENNIS_SEASONS=2025,2024,2023
HARVEST_MAX_TOURNAMENTS=0
HARVEST_CONCURRENCY=6

OUTPUT_FORMAT=csv
OUTPUT_DIR=./data
LOG_LEVEL=INFO
</code></pre>

<h3>🔹 Varredura de odds (<code>odds_harvest</code>)</h3>
<pre><code>API_BASE_URL=https://api.api-tennis.com/tennis
API_KEY=SEU_API_KEY_AQUI
ENDPOINT_PATH=/
ITEM_KEY=result

PAGINATION_MODE=odds_harvest
TENNIS_SEASONS=2025,2024
HARVEST_CONCURRENCY=6

OUTPUT_FORMAT=csv
OUTPUT_DIR=./data
LOG_LEVEL=INFO
</code></pre>

<hr>

<h2>▶️ Como Rodar</h2>
<pre><code># com a venv ativa, a partir da raiz do projeto
python -m src.run_async
</code></pre>
<p><strong>Saídas padrão</strong> (em <code>./data</code>):</p>
<ul>
  <li><code>resources_async.csv</code> — single/page/cursor</li>
  <li><code>players_harvest.csv</code> — players_harvest</li>
  <li><code>odds_harvest.csv</code> — odds_harvest</li>
  <li><code>state.json</code> — histórico incremental/coverage</li>
</ul>

<hr>

<h2>📈 Logs &amp; Cobertura</h2>
<pre><code>2025-10-16 14:26:12 | INFO | api_extractor.async | Iniciando HARVEST ...
2025-10-16 14:26:35 | INFO | api_extractor.async | Torneios considerados: 48
2025-10-16 14:26:58 | INFO | api_extractor.async | Player keys únicos encontrados: 566
2025-10-16 14:27:01 | INFO | api_extractor.async | Perfis coletados: 566. Normalizando...
2025-10-16 14:27:02 | INFO | api_extractor.async | Arquivo salvo (csv) em: ./data/players_harvest.csv
[COVERAGE] previous_keys=566 new_keys_this_run=0 total_unique=566
</code></pre>

<hr>

<h2>🗄️ Postgres (opcional)</h2>
<p>Defina no <code>.env</code>:</p>
<pre><code>POSTGRES_URL=postgresql+psycopg2://user:senha@localhost:5432/api_data
</code></pre>
<p>O script cria/alimenta as tabelas (<code>resources</code>, <code>players</code>, <code>odds</code>). Para UPSERT real (chave primária/merge), ajuste o schema/constraints conforme sua necessidade.</p>

<hr>

<h2>🧠 Customizações rápidas</h2>
<table>
  <thead><tr><th>Ação</th><th>Onde mudar</th></tr></thead>
  <tbody>
    <tr><td>Header de auth (ex.: <code>X-API-Key</code>)</td><td>função <code>_auth_headers()</code> em <code>run_async.py</code></td></tr>
    <tr><td>Chave de lista (<code>result</code> / <code>data</code> / <code>items</code>)</td><td><code>.env</code> → <code>ITEM_KEY</code></td></tr>
    <tr><td>Nome de tabela no Postgres</td><td>chamadas <code>upsert_postgres(...)</code></td></tr>
    <tr><td>Fallback para CSV</td><td>já implementado em <code>storage.py</code></td></tr>
    <tr><td>Escopo do harvest</td><td><code>.env</code> → <code>TENNIS_SEASONS</code>, <code>HARVEST_MAX_TOURNAMENTS</code></td></tr>
  </tbody>
</table>

<hr>

<h2>🧩 Extensões futuras</h2>
<ul>
  <li>Harvest de rankings, head-to-head e detalhes de torneios</li>
  <li>Agendador (cron/Airflow) e pipelines</li>
  <li>BigQuery/S3</li>
  <li>Exports incrementais diários</li>
</ul>

<hr>