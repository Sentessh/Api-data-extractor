import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Carrega variáveis do .env (se existir)
load_dotenv()

@dataclass(frozen=True)
class AppConfig:
    api_base_url: str
    api_key: Optional[str]
    api_auth_type: str  # "api_key" | "bearer" | "basic" (para este esqueleto usaremos bearer/api_key)
    page_param: str
    page_size_param: str
    page_size: int
    output_dir: str
    postgres_url: Optional[str]
    rate_limit_per_minute: int
    concurrency: int
    request_timeout_sec: int
    item_key: Optional[str]  # chave no JSON onde ficam os itens ("data", "results", etc.)

def load_config() -> AppConfig:
    api_base = os.getenv("API_BASE_URL", "").strip().rstrip("/")
    if not api_base:
        raise ValueError("API_BASE_URL não definido no .env")

    return AppConfig(
        api_base_url=api_base,
        api_key=os.getenv("API_KEY") or None,
        api_auth_type=os.getenv("API_AUTH_TYPE", "api_key").lower(),
        page_param=os.getenv("PAGE_PARAM", "page"),
        page_size_param=os.getenv("PAGE_SIZE_PARAM", "limit"),
        page_size=int(os.getenv("PAGE_SIZE", "100")),
        output_dir=os.getenv("OUTPUT_DIR", "./data"),
        postgres_url=os.getenv("POSTGRES_URL") or None,
        rate_limit_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")),
        concurrency=int(os.getenv("CONCURRENCY", "4")),
        request_timeout_sec=int(os.getenv("REQUEST_TIMEOUT_SEC", "30")),
        item_key=(os.getenv("ITEM_KEY") or "").strip() or None,
    )