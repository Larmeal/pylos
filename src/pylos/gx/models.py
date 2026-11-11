"""The ``validation`` section of a config: the contract, its expectations and the Data Docs setting."""

import hashlib
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, computed_field, model_validator

_RESERVED_META_KEYS = frozenset(
    {
        "expectation_key",
    }
)


class ExpectationConfig(BaseModel):
    """Configuration for a single Great Expectations rule.

    Attributes:
        expectation_type: The name of the GX expectation.
        kwargs: The arguments passed to the expectation.
        meta: Additional custom metadata for the expectation.
        notes: Free-form text notes for data documentation.
        description: A clear description of why this rule exists.
        name: An optional stable key for this rule, used in reports.
        severity: The severity level if this expectation fails. Required.
    """

    expectation_type: str = Field(
        description="The name of the GX expectation (e.g., 'expect_column_values_to_not_be_null')."
    )
    kwargs: dict[str, Any] = Field(
        default_factory=dict,
        description="The keyword arguments passed to the expectation (e.g., {'column': 'id'}).",
    )
    meta: dict[str, Any] = Field(
        default_factory=dict,
        validate_default=True,
        description="Additional custom metadata for the expectation (e.g., {'data_quality_issue': 'completeness'}).",
    )
    notes: str | list[str] | None = Field(
        default=None,
        description="Free-form text notes for data documentation.",
    )
    description: str | None = Field(
        default=None,
        description="A clear description of why this rule exists.",
    )
    name: str | None = Field(
        default=None,
        description=(
            "A readable name for the rule, shown in the report. If omitted, the contract fills in "
            "'<contract name>_<expectation_type>'."
        ),
    )
    severity: Literal["critical", "warning", "info"] = Field(
        default="critical",
        description=(
            "The severity level if this expectation fails. 'critical' triggers the failure action, 'warning' and 'info' are recorded only. Defaults to 'critical'."
        ),
    )

    @computed_field
    @property
    def expectation_key(self) -> str:
        """Stable identity of this rule: a SHA-256 of its type and kwargs.

        Two rules with the same ``expectation_type`` and ``kwargs`` get the same
        key. The kwargs are hashed as written, so the same kwargs in a different
        order give a different key. The key is copied into ``meta`` (see
        ``_reserved_meta_keys``) because ``meta`` is the only field GX echoes back
        in its result, and that is how ``GXTranslateExpectationResult`` matches
        each result to its rule.
        """
        return hashlib.sha256(f"{self.expectation_type}-{self.kwargs}".encode()).hexdigest()

    @model_validator(mode="after")
    def _reserved_meta_keys(self) -> Self:
        """Reject ``meta`` that uses a reserved key, then add ``expectation_key`` to it.

        ``expectation_key`` belongs to Pylos. A user value under that name would
        be silently overwritten here, so it is refused at load time instead.

        Raises:
            ValueError: ``meta`` contains a key from ``_RESERVED_META_KEYS``.
        """
        # Ensure that reserved meta keys are not used in the meta dictionary
        # For set type, Use '&' to find the intersection with the keys of the meta dictionary
        if collision := _RESERVED_META_KEYS & self.meta.keys():
            raise ValueError(f"meta key(s) {sorted(collision)} are reserved for Pylos internal use")
        self.meta.update({"expectation_key": self.expectation_key})
        return self


class ContractConfig(BaseModel):
    """The contract for a dataset: the rules it must satisfy.

    Attributes:
        data_asset_name: The contract's name, written as `name:` in YAML.
        description: A description of the contract's purpose.
        expectations: The rules to apply to every source object.
    """

    data_asset_name: str = Field(description="The name of the data asset.", alias="name")
    datasource_name: str | None = Field(
        default=None,
        description="The name of the GX datasource.",
    )
    batch_definition_name: str | None = Field(
        default=None,
        description="The name of the batch definition (V1.x architecture).",
    )
    expectation_suite_name: str | None = Field(
        default=None,
        description="The name used to register the suite.",
    )
    description: str | None = Field(
        default=None,
        description="A description of the contract's purpose.",
    )
    expectations: list[ExpectationConfig] = Field(
        description="The nested expectation suite configuration containing all expectations."
    )

    @model_validator(mode="after")
    def _resolve_gx_names(self) -> Self:
        """Fill in any GX name the YAML left out, derived from the contract's ``name``.

        GX needs a datasource, batch definition and suite name. Unset ones become
        ``<name>_source``, ``<name>_batch`` and ``<name>_suite``. Names set in the
        YAML are kept.
        """
        self.datasource_name = self.datasource_name or f"{self.data_asset_name}_source"
        self.batch_definition_name = self.batch_definition_name or f"{self.data_asset_name}_batch"
        self.expectation_suite_name = self.expectation_suite_name or f"{self.data_asset_name}_suite"
        return self

    @model_validator(mode="after")
    def _name_unnamed_expectations(self) -> Self:
        """Give every expectation without a ``name`` the default ``<contract name>_<expectation_type>``.

        The report carries each rule's name, so a rule left unnamed would show ``null``
        there. A name set in the YAML is kept. An empty name counts as unset.

        The default is not unique: two rules of the same type on different columns get
        the same name. ``expectation_key`` is what tells them apart, so give such rules
        an explicit ``name`` when you want to read them apart in a report.
        """
        for expectation in self.expectations:
            if not expectation.name:
                expectation.name = f"{self.data_asset_name}_{expectation.expectation_type}"
        return self


class DataDocsConfig(BaseModel):
    """Configuration for Great Expectations Data Docs.

    Attributes:
        enabled: Whether to render the site at all. Off by default.
        store_path: Where to write it. Nothing is persisted when omitted.
    """

    enabled: bool = Field(
        default=False,
        description="Indicates whether Data Docs generation is enabled.",
    )
    store_path: str | None = Field(
        default=None,
        description="The path where Data Docs will be stored.",
    )

    @model_validator(mode="after")
    def _validate_store_path_if_enabled(self) -> Self:
        """Require ``store_path`` when Data Docs is enabled, and make it absolute.

        A relative ``store_path`` is resolved against the current directory at
        load time, so it keeps pointing at the same place if the working
        directory changes later.

        Raises:
            ValueError: ``enabled`` is true and ``store_path`` is missing or empty.
        """
        if self.enabled and not self.store_path:
            raise ValueError("store_path must be specified if Data Docs are enabled")
        if self.store_path is not None:
            self.store_path = str(Path(self.store_path).resolve())
        return self


class GXConfig(BaseModel):
    """The `validation:` section of the configuration.

    Attributes:
        contract: The rules to apply, and what each failure means.
        data_docs: Whether to render an HTML view of the results, and where.
    """

    contract: ContractConfig = Field(
        description="The contract for the dataset, including its expectations.",
    )
    data_docs: DataDocsConfig = Field(
        default_factory=DataDocsConfig,
        description="Configuration for Great Expectations Data Docs. Omitted means disabled.",
    )
