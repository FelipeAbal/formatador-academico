"""Product Input Boundary v0.1 composition (decision 0043)."""
from __future__ import annotations

from ..processing_session import DEFAULT_MAX_APPLIED_OPERATIONS
from ..product_output_bundle import (
    ProductOutputBundle,
    ProductOutputBundleContractError,
    ProductOutputBundleIntegrityError,
    build_product_output_bundle,
)
from ..profile_input import (
    ProfileInputContractError,
    ProfileInputUnsupportedError,
    processing_profile_from_json,
)
from .model import (
    ProductInputBoundaryContractError,
    ProductInputBoundaryIntegrityError,
    ProductInputBoundaryUnsupportedError,
    ProductInputStage,
)


def build_product_from_inputs(
    package_snapshot: bytes,
    profile_json_bytes: bytes,
    *,
    max_applied_operations: int = DEFAULT_MAX_APPLIED_OPERATIONS,
) -> ProductOutputBundle:
    """Compose frozen Profile Input + Product Output Bundle boundaries."""

    # External type order is frozen for deterministic first-error behavior.
    if type(package_snapshot) is not bytes:
        raise ProductInputBoundaryContractError(
            "external_input.package_type",
            "package_snapshot must be exact bytes",
            ProductInputStage.EXTERNAL_INPUT,
        )
    if type(profile_json_bytes) is not bytes:
        raise ProductInputBoundaryContractError(
            "external_input.profile_type",
            "profile_json_bytes must be exact bytes",
            ProductInputStage.EXTERNAL_INPUT,
        )

    try:
        profile = processing_profile_from_json(profile_json_bytes)
    except ProfileInputUnsupportedError as exc:
        raise ProductInputBoundaryUnsupportedError(
            f"profile_input.{exc.code}",
            exc.message,
            ProductInputStage.PROFILE_INPUT,
        ) from exc
    except ProfileInputContractError as exc:
        raise ProductInputBoundaryContractError(
            f"profile_input.{exc.code}",
            exc.message,
            ProductInputStage.PROFILE_INPUT,
        ) from exc

    try:
        return build_product_output_bundle(
            package_snapshot,
            profile,
            max_applied_operations=max_applied_operations,
        )
    except ProductOutputBundleContractError as exc:
        raise ProductInputBoundaryContractError(
            "product_output.contract",
            str(exc),
            ProductInputStage.PRODUCT_OUTPUT,
        ) from exc
    except ProductOutputBundleIntegrityError as exc:
        raise ProductInputBoundaryIntegrityError(
            "product_output.integrity",
            str(exc),
            ProductInputStage.PRODUCT_OUTPUT,
        ) from exc
