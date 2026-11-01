from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterable

import pandas as pd

from vision.auth import AuthConfigurationError, AuthSettings, Principal, RoleAssignment


class AuthorizationRegistry:
    """Maps authenticated subjects to independently configured VISION scopes."""

    def __init__(self, assignments: dict[str, RoleAssignment]):
        self._assignments = assignments

    @classmethod
    def from_env(
        cls,
        settings: AuthSettings,
        environ: dict[str, str] | None = None,
    ) -> AuthorizationRegistry:
        values = os.environ if environ is None else environ
        try:
            rows = json.loads(values["VISION_AUTHZ_ASSIGNMENTS_JSON"])
        except (KeyError, json.JSONDecodeError) as exc:
            raise AuthConfigurationError(
                "VISION_AUTHZ_ASSIGNMENTS_JSON is required and must be valid JSON."
            ) from exc
        from vision.auth import _parse_assignments

        assignments = _parse_assignments(rows)
        if set(settings.users) != set(assignments):
            raise AuthConfigurationError(
                "Every temporary identity must have exactly one authorization assignment."
            )
        return cls(assignments)

    def assignment(self, principal: Principal) -> RoleAssignment | None:
        return self._assignments.get(principal.subject.casefold())


class AuthorizationDenied(PermissionError):
    pass


def assigned_scope(
    assignment: RoleAssignment, scope_name: str
) -> str | tuple[str, ...]:
    scope = assignment.scope.get(scope_name)
    if scope is None:
        raise AuthorizationDenied("The signed-in user has no scope for this operation.")
    return scope


def restrict_rows_to_stages(
    model: pd.DataFrame,
    allowed_stages: Iterable[str],
    classify_stages: Callable[[pd.DataFrame], pd.Series],
) -> pd.DataFrame:
    allowed = frozenset(allowed_stages)
    if not allowed:
        raise AuthorizationDenied("The signed-in user has no permitted stages.")
    stages = classify_stages(model)
    mask = stages.map(lambda values: bool(allowed.intersection(values)))
    return model.loc[mask].copy()


def visible_stages(values: Iterable[str], allowed_stages: Iterable[str]) -> list[str]:
    allowed = frozenset(allowed_stages)
    return [value for value in values if value in allowed]
