# -*- coding: utf-8 -*-
"""Cadastral Attribute KVKK / GDPR De-identification and Anonymizer Engine for NCZ2Geo."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Iterable

from .ncz_engine.model import NetcadAttributeRow, NetcadAttributeTable, NetcadParseResult

# Common Turkish cadastral PII column keys
PII_COLUMN_PATTERNS = [
    r"AD.*SOYAD",
    r"MALIK",
    r"TC_?KIMLIK",
    r"TCK?N",
    r"BABA_?ADI",
    r"ANA_?ADI",
    r"TELEFON",
    r"GSM",
    r"EMAIL",
    r"VERGI_?NO",
    r"HISS?E",
    r"PAYDAS",
]


@dataclass
class AnonymizationReport:
    """Summary metrics of cadastral data scrubbing."""

    total_tables: int
    total_rows: int
    total_pii_fields_scrubbed: int
    scrubbed_columns: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_tables": self.total_tables,
            "total_rows": self.total_rows,
            "total_pii_fields_scrubbed": self.total_pii_fields_scrubbed,
            "scrubbed_columns": self.scrubbed_columns,
        }


def mask_pii_value(val: str, salt: str = "ncz2geo_salt") -> str:
    """Mask or pseudonymize a sensitive cadastral string using truncated SHA-256 hash."""
    if not val:
        return ""
    h = hashlib.sha256((val + salt).encode("utf-8")).hexdigest()[:8].upper()
    return f"ANON_{h}"


def anonymize_ncz_attributes(
    attribute_tables: Iterable[NetcadAttributeTable],
    salt: str = "ncz2geo_salt",
) -> tuple[list[NetcadAttributeTable], AnonymizationReport]:
    """Scrub PII from Netcad attribute tables while preserving table schema and linkage."""
    cleaned_tables: list[NetcadAttributeTable] = []
    total_rows = 0
    total_scrubbed = 0
    scrubbed_cols_set: set[str] = set()

    for table in attribute_tables:
        cleaned_rows: list[NetcadAttributeRow] = []
        for row in table.rows:
            total_rows += 1
            new_cols: dict[str, str] = {}
            for col_name, col_val in row.columns.items():
                is_pii = any(re.search(pat, col_name, re.IGNORECASE) for pat in PII_COLUMN_PATTERNS)
                if is_pii:
                    new_cols[col_name] = mask_pii_value(col_val, salt=salt)
                    total_scrubbed += 1
                    scrubbed_cols_set.add(col_name)
                else:
                    new_cols[col_name] = col_val

            cleaned_rows.append(
                NetcadAttributeRow(
                    row_index=row.row_index,
                    columns=new_cols,
                )
            )

        cleaned_tables.append(
            NetcadAttributeTable(
                table_ref=table.table_ref,
                rows=cleaned_rows,
            )
        )

    report = AnonymizationReport(
        total_tables=len(cleaned_tables),
        total_rows=total_rows,
        total_pii_fields_scrubbed=total_scrubbed,
        scrubbed_columns=sorted(scrubbed_cols_set),
    )
    return cleaned_tables, report
