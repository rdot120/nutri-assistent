"""
Entry point da GUI de automacao nutricional.
"""
import sys
from pathlib import Path

# Adicionar diretorio ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gui.app import App


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
