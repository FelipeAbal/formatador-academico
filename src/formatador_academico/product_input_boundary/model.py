"""Product Input Boundary v0.1 public error model (decision 0043)."""
from __future__ import annotations

from enum import Enum

PRODUCT_INPUT_BOUNDARY_VERSION = "0.1"


class ProductInputStage(str, Enum):
    EXTERNAL_INPUT = "external_input"
    PROFILE_INPUT = "profile_input"
    PRODUCT_OUTPUT = "product_output"


class ProductInputBoundaryError(Exception):
    """Base user-facing product input boundary error."""

    def __init__(self, code: str, message: str, stage: ProductInputStage):
        super().__init__(message)
        if not isinstance(code, str) or not code:
            raise ValueError("ProductInputBoundaryError.code must be non-empty")
        if not isinstance(message, str) or not message:
            raise ValueError("ProductInputBoundaryError.message must be non-empty")
        if not isinstance(stage, ProductInputStage):
            raise TypeError("ProductInputBoundaryError.stage must be ProductInputStage")
        self.code = code
        self.message = message
        self.stage = stage


class ProductInputBoundaryContractError(ProductInputBoundaryError, ValueError):
    """Malformed external input or downstream contract failure."""


class ProductInputBoundaryUnsupportedError(ProductInputBoundaryError):
    """Well-formed Profile Input outside current schema/capability."""


class ProductInputBoundaryIntegrityError(ProductInputBoundaryError):
    """Impossible downstream lineage/integrity contradiction."""
