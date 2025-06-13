"""
Henry is the high-level client for hippo. Lower-level functions are available
in `hippoclient`.
"""

from .core import Henry
from .source import LocalSource

__all__ = ["Henry", "LocalSource"]
