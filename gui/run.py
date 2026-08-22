"""
Entry point da GUI de automacao nutricional.
"""
import sys
import logging
from pathlib import Path

# Adicionar diretorio ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import DATA_DIR


def _setup_logging():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(DATA_DIR / "app.log",
                                encoding="utf-8"),
        ],
    )


def main():
    _setup_logging()
    from gui.app import App
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
