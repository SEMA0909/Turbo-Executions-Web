"""Entry point: `python -m app.main`."""
from __future__ import annotations
import logging
import uvicorn
from app.config import settings


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    uvicorn.run("app.api.server:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
python 