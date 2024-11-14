from typing import Literal

from pydantic import Field

from .base import BaseMetadata


class NumericMetadata(BaseMetadata):
    """
    A simple metadata type for a numeric value.
    """

    metadata_type: Literal["numeric"] = "numeric"

    value: float = Field(min=-1e100, max=1e100)
