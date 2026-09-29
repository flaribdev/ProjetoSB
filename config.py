"""config.py — configurações centrais do projeto."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DB = RAIZ / "indicadores.db"