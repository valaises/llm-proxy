import asyncio

import uvloop
import uvicorn

from core.args import parse_args
from core.logger import init_logger, info, error
from core.models import get_assets_models
from core.globals import BASE_DIR, SECRET_KEY
from core.app import App


def main():
    assert SECRET_KEY, "LLM_PROXY_SECRET is not set"
    init_logger(False)
    args = parse_args()
    init_logger(args.DEBUG)
    info("logger initialized")

    a_models = get_assets_models(BASE_DIR)
    if not a_models.model_list:
        error("No models available. Exiting...")
        quit(0)

    db_dir = BASE_DIR / "db"
    db_dir.mkdir(parents=True, exist_ok=True)

    app = App(
        db_dir,
        a_models,
        docs_url=None, redoc_url=None
    )

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        timeout_keep_alive=600,
        log_config=None
    )


if __name__ == "__main__":
    main()
