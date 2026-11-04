"""
A simple python wrapper for the HTTP for hippo.

API key can be stored in the hippo_API_KEY environment variable.
Host can be stored in the hippo_HOST environment variable.
"""

__all__ = [
    "Client",
    "caching",
    "collections",
    "product",
    "relationships",
]

from . import caching, collections, product, relationships
from .core import Client
