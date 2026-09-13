"""Strongly typed identifiers with shared syntax validation."""

import re
from typing import Self

from pydantic import ConfigDict, RootModel, field_validator

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")


class Identifier(RootModel[str]):
    """Validated opaque identifier; it carries no authority or trading behavior."""

    model_config = ConfigDict(frozen=True)

    @field_validator("root")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("identifier cannot contain leading or trailing whitespace")
        if not _IDENTIFIER.fullmatch(value):
            raise ValueError(
                "identifier must be 1-128 characters and use letters, digits, "
                "'.', '_', ':', '/', or '-'"
            )
        segments = value.replace(":", "/").split("/")
        if any(segment in {"", ".", ".."} for segment in segments):
            raise ValueError("identifier cannot contain empty or traversal segments")
        return value

    def __str__(self) -> str:
        return self.root

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.root!r})"

    @classmethod
    def parse(cls, value: str) -> Self:
        return cls.model_validate(value)


class AgentId(Identifier):
    """Identity of an isolated trading participant."""


class AccountId(Identifier):
    """Identity of a logically isolated account boundary."""


class AllocationId(Identifier):
    """Identity of an attributed capital allocation boundary."""


class ExperimentId(Identifier):
    """Identity of an immutable experiment run or registration."""


class StrategyId(Identifier):
    """Identity of a strategy independently from its model."""


class ModelId(Identifier):
    """Identity of an optional AI model independently from strategy."""


class ConfigurationVersionId(Identifier):
    """Identity of a versioned resolved configuration."""


class InstrumentId(Identifier):
    """Identity of a canonical tradable instrument."""


class DatasetId(Identifier):
    """Content-derived identity of an immutable market-data dataset."""


class IndicatorConfigurationId(Identifier):
    """Content-derived identity of an immutable indicator configuration."""
