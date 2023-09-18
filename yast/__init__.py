__version__ = "0.2.5"
__description__ = "yet another startlette as yast"

__all__ = ["Yast", "TestClient"]

from .applications import Yast
from .testclient import TestClient
