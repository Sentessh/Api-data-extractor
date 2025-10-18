# src/run_async.py
import asyncio
import os
from typing import Any, Dict, Iterable, List, Optional

# --- import fallback para permitir `python src/run_async.py` e `python -m src.run_async` ---
try:
    from src.config import load_config
    from src.logger import setup_logger
    from src.async_client import AsyncHTTPClient
    from src.normalizer import flatten_items_to_df
    from src.storage import save_parquet, save_csv, upsert_postgres
except ModuleNotFoundError:
    import sys
    ROOT = os.path.dirname(os.path.dirname(__file__))  # .../Api-data-extractor
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from src.config import load_config
    from src.logger import setup_logger
    from src.async_client import AsyncHTTPClient
    from src.normalizer import flatten_items_to_df
    from src.storage import save_parquet, save_csv, upsert_postgres
# --- fim do fallback ---

logger = setup_logger("api_extractor.async")


def _auth_headers(api_key: Optional[str], auth_type: str) -> Dict[str, str]:
    """
    Ajuste aqui se a API exigir header específico (ex.: 'X-API-Key').
    Para a API Tennis, não usamos header — a key vai em 'APIkey' na query string.
    """
    if not api_key:
        return {}
    if auth_type == "bearer":
        return {"Authorization": f"Bearer {api_key}"}
    if auth_type == "api_key":
        # Exemplo genérico; personalize conforme a API real
        return {"Authorization": api_key}
    if auth_type == "basic":
        return {"Authorization": api_key}
    return {}


async def iter_paginated(
    client: AsyncHTTPClient,
    path: str,
    params: Dict[str, Any],
    page_param: str,
    size_param: str,
    page_size: int,
    item_key: Optional[str],
) -> Iterable[Dict[str, Any]]: # type: ignore
    """
    Paginação por número de página.
    """
    page = 1
    while True:
        q = dict(params)
        q[page_param] = page
        q[size_param] = page_size
        j = await client.get_json(path, params=q)
        # Descobrir lista de itens
        items: List[Dict[str, Any]] = []
        if isinstance(j, list):
            items = j
        elif isinstance(j, dict):
            if item_key:
                items = j.get(item_key, []) or []
            else:
                # heurística: primeira lista do dict
                for v in j.values():
                    if isinstance(v, list):
                        items = v
                        break

        if not items:
            logger.debug("Sem itens retornados; encerrando paginação.")
            break

        for it in items:
            yield it

        if len(items) < page_size:
            break
        page += 1


async def iter_cursor(
    client: AsyncHTTPClient,
    path: str,
    params: Dict[str, Any],
    cursor_param: str = "cursor",
    cursor_field: str = "next",
    item_key: Optional[str] = None,
) -> Iterable[Dict[str, Any]]: # type: ignore
    """
    Paginação por cursor/token.
    """
    q = dict(params)
    cursor: Optional[str] = None
    while True:
        if cursor:
            q[cursor_param] = cursor
        j = await client.get_json(path, params=q)
        items: List[Dict[str, Any]] = []
        if isinstance(j, list):
            items = j
            next_cursor = None
        elif isinstance(j, dict):
            if item_key:
                items = j.get(item_key, []) or []
            else:
                items = j.get("data", []) or j.get("results", []) or []
            next_cursor = j.get(cursor_field)
        else:
            next_cursor = None

        for it in items:
            yield it

        if not next_cursor:
            break
        cursor = next_cursor


async def main():
    cfg = load_config()

    # Formato de saída configurável: "parquet" (default) ou "csv"
    output_format = os.getenv("OUTPUT_FORMAT", "parquet").lower().strip()

    # Endpoint/rota base (ex.: "/v1/resources" ou "/" para a Tennis API)
    endpoint_path = os.getenv("ENDPOINT_PATH", "/v1/resources")

    # Modo de paginação: "single" (um GET), "page", "cursor", "players_harvest"
    pagination_mode = os.getenv("PAGINATION_MODE", "page").lower().strip()

    # --- Preset para API Tennis (params via query) ---
    # Você pode desabilitar removendo/alterando estas variáveis no .env.
    # Se não for Tennis, basta sobrescrever base_params abaixo.
    base_params: Dict[str, Any] = {
        "method": os.getenv("TENNIS_METHOD", "get_players"),
        "APIkey": os.getenv("API_KEY", ""),  # a Tennis usa a mesma key, mas na query
    }
    pk = os.getenv("TENNIS_PLAYER_KEY")
    if pk:
        base_params["player_key"] = pk

    # Cabeçalhos (para APIs que precisam de Authorization em header)
    headers = _auth_headers(cfg.api_key, cfg.api_auth_type)

    # Caminho base do arquivo de saída (sem extensão)
    out_base = os.path.join(cfg.output_dir, "resources_async")
    os.makedirs(cfg.output_dir, exist_ok=True)

    # ------------------------ MODO SINGLE ------------------------
    if pagination_mode == "single":
        # Request único (ideal para APIs estilo "method=...&APIkey=...")
        async with AsyncHTTPClient(
            base_url=cfg.api_base_url,
            headers={},  # Tennis API: auth via query, não header
            rate_per_minute=cfg.rate_limit_per_minute,
            concurrency=cfg.concurrency,
            request_timeout_sec=cfg.request_timeout_sec,
        ) as client:
            logger.info(f"Iniciando extração assíncrona de {cfg.api_base_url}{endpoint_path} (modo=single)")
            method = os.getenv("TENNIS_METHOD", "get_players")
            api_key = os.getenv("API_KEY", "")

            # lê TENNIS_PLAYER_KEYS (lista) OU TENNIS_PLAYER_KEY (único)
            keys_env = os.getenv("TENNIS_PLAYER_KEYS")
            key_single = os.getenv("TENNIS_PLAYER_KEY")
            player_keys = []
            if keys_env:
                player_keys = [k.strip() for k in keys_env.split(",") if k.strip()]
            elif key_single:
                player_keys = [key_single]

            all_items: List[Dict[str, Any]] = []

            if player_keys:
                # loop por cada player_key
                for one_pk in player_keys:
                    params = {"method": method, "APIkey": api_key, "player_key": one_pk}
                    j = await client.get_json(endpoint_path, params=params)
                    key = cfg.item_key or "result"
                    items = j.get(key, []) if isinstance(j, dict) else (j if isinstance(j, list) else [])
                    if not items:
                        logger.warning(f"Nenhum item para player_key={one_pk}. Resposta: {repr(j)[:300]}")
                        continue
                    all_items.extend(items)
            else:
                # sem player_key -> a API exige para get_players
                raise SystemExit("Esta API exige 'player_key' para get_players. Defina TENNIS_PLAYER_KEY ou TENNIS_PLAYER_KEYS no .env.")

            if not all_items:
                logger.warning("Nenhum item retornado.")
                return

            logger.info(f"Itens coletados: {len(all_items)}. Normalizando...")
            df = flatten_items_to_df(all_items)

            if output_format == "csv":
                saved_path = save_csv(df, out_base + ".csv")
                logger.info(f"Arquivo salvo (csv) em: {saved_path}")
            else:
                saved_path, saved_fmt = save_parquet(df, out_base + ".parquet")
                logger.info(f"Arquivo salvo ({saved_fmt}) em: {saved_path}")

            if cfg.postgres_url:
                upsert_postgres(df, table_name="resources", pg_url=cfg.postgres_url)
                logger.info("Gravação no Postgres concluída.")
        return

    # ------------------- MODO PLAYERS_HARVEST -------------------
    elif pagination_mode == "players_harvest":
        # Descobre player_keys a partir de fixtures, depois puxa perfis via get_players.
        async with AsyncHTTPClient(
            base_url=cfg.api_base_url,
            headers={},  # auth via query na Tennis API
            rate_per_minute=cfg.rate_limit_per_minute,
            concurrency=int(os.getenv("HARVEST_CONCURRENCY", str(cfg.concurrency))),
            request_timeout_sec=cfg.request_timeout_sec,
        ) as client:
            logger.info(f"Iniciando HARVEST de players via tournaments/fixtures em {cfg.api_base_url}{endpoint_path}")

            api_key = os.getenv("API_KEY", "")
            # 1) Torneios
            tournaments_resp = await client.get_json(endpoint_path, params={"method": "get_tournaments", "APIkey": api_key})
            tournaments = tournaments_resp.get("result", []) if isinstance(tournaments_resp, dict) else []
            if not tournaments:
                raise SystemExit("Nenhum torneio retornado por get_tournaments — confira sua API_KEY/plan.")
            max_t = int(os.getenv("HARVEST_MAX_TOURNAMENTS", "0")) or None
            if max_t:
                tournaments = tournaments[:max_t]
            logger.info(f"Torneios considerados: {len(tournaments)}")

            # 2) Escolha de temporadas / datas
            seasons_env = os.getenv("TENNIS_SEASONS")
            seasons = [s.strip() for s in seasons_env.split(",")] if seasons_env else []
            date_start = os.getenv("TENNIS_DATE_START")
            date_stop  = os.getenv("TENNIS_DATE_STOP")

            player_keys = set()

            async def fetch_fixture_keys_for_tournament(t):
                tkey = t.get("tournament_key")
                if not tkey:
                    return []
                found = set()
                # A) por seasons
                if seasons:
                    for season in seasons:
                        params = {"method": "get_fixtures", "APIkey": api_key, "tournament_key": tkey, "tournament_season": season}
                        j = await client.get_json(endpoint_path, params=params)
                        res = j.get("result", []) if isinstance(j, dict) else []
                        for ev in res:
                            fk = ev.get("first_player_key")
                            sk = ev.get("second_player_key")
                            if fk: found.add(str(fk))
                            if sk: found.add(str(sk))
                # B) por intervalo de datas
                elif date_start and date_stop:
                    params = {"method": "get_fixtures", "APIkey": api_key, "tournament_key": tkey, "date_start": date_start, "date_stop": date_stop}
                    j = await client.get_json(endpoint_path, params=params)
                    res = j.get("result", []) if isinstance(j, dict) else []
                    for ev in res:
                        fk = ev.get("first_player_key")
                        sk = ev.get("second_player_key")
                        if fk: found.add(str(fk))
                        if sk: found.add(str(sk))
                else:
                    # fallback: tenta sem filtros (se o provedor devolver algo)
                    params = {"method": "get_fixtures", "APIkey": api_key, "tournament_key": tkey}
                    j = await client.get_json(endpoint_path, params=params)
                    res = j.get("result", []) if isinstance(j, dict) else []
                    for ev in res:
                        fk = ev.get("first_player_key")
                        sk = ev.get("second_player_key")
                        if fk: found.add(str(fk))
                        if sk: found.add(str(sk))
                return list(found)

            # 3) Coleta keys de todos os torneios em paralelo
            tasks = [asyncio.create_task(fetch_fixture_keys_for_tournament(t)) for t in tournaments]
            for coro in asyncio.as_completed(tasks):
                try:
                    keys = await coro
                    player_keys.update(keys)
                except Exception as e:
                    logger.warning(f"Falha ao coletar keys de um torneio: {e}")

            logger.info(f"Player keys únicos encontrados: {len(player_keys)}")

            if not player_keys:
                logger.warning("Nenhuma player_key encontrada em fixtures. Verifique filtros (seasons/dates).")
                return

            # 4) Fan-out: perfis via get_players (em lotes para respeitar limite)
            keys_list = list(player_keys)
            all_profiles: List[dict] = []

            sem = asyncio.Semaphore(int(os.getenv("HARVEST_CONCURRENCY", str(cfg.concurrency))))
            async def fetch_player(one_pk: str):
                async with sem:
                    j = await client.get_json(endpoint_path, params={"method": "get_players", "APIkey": api_key, "player_key": one_pk})
                    if isinstance(j, dict):
                        items = j.get(os.getenv("ITEM_KEY", "result"), []) or []
                    else:
                        items = j if isinstance(j, list) else []
                    return items

            fetch_tasks = [asyncio.create_task(fetch_player(one_pk)) for one_pk in keys_list]
            for coro in asyncio.as_completed(fetch_tasks):
                try:
                    items = await coro
                    if items:
                        all_profiles.extend(items)
                except Exception as e:
                    logger.warning(f"Falha ao obter perfil de jogador: {e}")

            if not all_profiles:
                logger.warning("Nenhum perfil retornado por get_players.")
                return

            logger.info(f"Perfis coletados: {len(all_profiles)}. Normalizando...")
            df = flatten_items_to_df(all_profiles)

            out_base = os.path.join(cfg.output_dir, "players_harvest")
            os.makedirs(cfg.output_dir, exist_ok=True)

            if os.getenv("OUTPUT_FORMAT", "parquet").lower() == "csv":
                saved_path = save_csv(df, out_base + ".csv")
                logger.info(f"Arquivo salvo (csv) em: {saved_path}")
            else:
                saved_path, saved_fmt = save_parquet(df, out_base + ".parquet")
                logger.info(f"Arquivo salvo ({saved_fmt}) em: {saved_path}")

            if cfg.postgres_url:
                upsert_postgres(df, table_name="players", pg_url=cfg.postgres_url)
                logger.info("Gravação no Postgres concluída.")
        return

    # ------------------- MODOS PAGE / CURSOR --------------------
    async with AsyncHTTPClient(
        base_url=cfg.api_base_url,
        headers=headers,
        rate_per_minute=cfg.rate_limit_per_minute,
        concurrency=cfg.concurrency,
        request_timeout_sec=cfg.request_timeout_sec,
    ) as client:
        logger.info(f"Iniciando extração assíncrona de {cfg.api_base_url}{endpoint_path} (modo={pagination_mode})")

        all_items: List[Dict[str, Any]] = []

        if pagination_mode == "cursor":
            async for item in iter_cursor(
                client,
                endpoint_path,
                params={},  # ajuste filtros aqui se quiser
                cursor_param=os.getenv("CURSOR_PARAM", "cursor"),
                cursor_field=os.getenv("CURSOR_FIELD", "next"),
                item_key=cfg.item_key,
            ):
                all_items.append(item)
        else:  # "page"
            async for item in iter_paginated(
                client,
                endpoint_path,
                params={},  # ajuste filtros aqui se quiser
                page_param=cfg.page_param,
                size_param=cfg.page_size_param,
                page_size=cfg.page_size,
                item_key=cfg.item_key,
            ):
                all_items.append(item)

    if not all_items:
        logger.warning("Nenhum item retornado.")
        return

    logger.info(f"Itens coletados: {len(all_items)}. Normalizando...")
    df = flatten_items_to_df(all_items)

    if output_format == "csv":
        saved_path = save_csv(df, out_base + ".csv")
        logger.info(f"Arquivo salvo (csv) em: {saved_path}")
    else:
        saved_path, saved_fmt = save_parquet(df, out_base + ".parquet")
        logger.info(f"Arquivo salvo ({saved_fmt}) em: {saved_path}")

    if cfg.postgres_url:
        upsert_postgres(df, table_name="resources", pg_url=cfg.postgres_url)
        logger.info("Gravação no Postgres concluída.")


if __name__ == "__main__":
    asyncio.run(main())