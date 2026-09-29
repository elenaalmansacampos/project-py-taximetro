"""Punto de entrada del taximetro.

El codigo vive en ``src/`` para que no se confunda con la raiz del proyecto.
Este ajuste anade ``src`` al path solo cuando el paquete no esta instalado,
de modo que ``python3 main.py`` funcione tanto en local como en la imagen.
"""

import sys
from pathlib import Path


SRC = Path(__file__).resolve().parent / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from taximeter.interfaces.cli import main  # noqa: E402


if __name__ == "__main__":
    main()
