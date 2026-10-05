# -*- coding: utf-8 -*-
"""PlanGML and e-Plan zoning plan compliance validator for NCZ2Geo."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .ncz_engine.model import NetcadParseResult
from .plangml import LayerClassification, classify_layer, detect_plan_type, normalize_layer_name
from .reader import NetcadReader


@dataclass(frozen=True)
class PlanValidationIssue:
    """Represents a specific issue or recommendation in a Netcad drawing."""

    severity: str  # 'ERROR', 'WARNING', 'INFO'
    category: str  # 'CLASSIFICATION', 'MANDATORY_LAYER', 'GEOMETRY', 'ATTRIBUTE'
    layer_name: str
    message: str
    code: str

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "category": self.category,
            "layer_name": self.layer_name,
            "message": self.message,
            "code": self.code,
        }


@dataclass
class PlanValidationReport:
    """Comprehensive compliance and quality assessment report for an urban plan."""

    plan_type: str
    total_layers: int
    matched_layers: int
    unmatched_layers: list[str]
    total_entities: int
    quality_score: float  # 0.0 to 100.0
    issues: list[PlanValidationIssue] = field(default_factory=list)
    land_use_breakdown: dict[str, int] = field(default_factory=dict)
    mandatory_layers_present: list[str] = field(default_factory=list)
    mandatory_layers_missing: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Return True if there are zero ERROR-level issues."""
        return not any(issue.severity == "ERROR" for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_type": self.plan_type,
            "is_valid": self.is_valid,
            "quality_score": round(self.quality_score, 2),
            "total_layers": self.total_layers,
            "matched_layers": self.matched_layers,
            "match_ratio": round(self.matched_layers / max(1, self.total_layers), 4),
            "unmatched_layers": self.unmatched_layers,
            "total_entities": self.total_entities,
            "mandatory_layers_present": self.mandatory_layers_present,
            "mandatory_layers_missing": self.mandatory_layers_missing,
            "land_use_breakdown": self.land_use_breakdown,
            "issues": [issue.to_dict() for issue in self.issues],
        }

    def to_markdown(self) -> str:
        """Render validation report as GitHub Flavored Markdown."""
        lines = [
            f"# PlanGML & e-Plan Compliance Report ({self.plan_type})",
            "",
            f"**Status**: {'✅ VALID' if self.is_valid else '❌ INVALID (Errors Found)'} | **Quality Score**: {self.quality_score:.1f}/100",
            "",
            "## Summary Metrics",
            f"- **Total Layers**: {self.total_layers}",
            f"- **Classified Layers**: {self.matched_layers} ({self.matched_layers / max(1, self.total_layers):.1%})",
            f"- **Total Entities**: {self.total_entities}",
            "",
        ]

        if self.mandatory_layers_missing:
            lines.append("## ⚠️ Missing Mandatory Layers")
            for m in self.mandatory_layers_missing:
                lines.append(f"- `{m}`")
            lines.append("")

        if self.land_use_breakdown:
            lines.append("## 📊 Land Use Function Breakdown")
            lines.append("| Function / Main Group | Entity Count |")
            lines.append("| --- | --- |")
            for name, count in sorted(self.land_use_breakdown.items(), key=lambda x: -x[1]):
                lines.append(f"| {name} | {count} |")
            lines.append("")

        if self.issues:
            lines.append("## 🔍 Issues and Warnings")
            lines.append("| Severity | Category | Layer | Message | Code |")
            lines.append("| --- | --- | --- | --- | --- |")
            for iss in self.issues:
                icon = "🔴" if iss.severity == "ERROR" else ("🟡" if iss.severity == "WARNING" else "ℹ️")
                lines.append(f"| {icon} {iss.severity} | {iss.category} | `{iss.layer_name}` | {iss.message} | `{iss.code}` |")
            lines.append("")

        return "\n".join(lines)


MANDATORY_PLAN_LAYERS: dict[str, list[str]] = {
    "UIP": ["ONAMA_SINIRI", "YOL", "ADA", "KONUT"],
    "NIP": ["ONAMA_SINIRI", "YOL", "KONUT"],
    "CDP": ["ONAMA_SINIRI", "CEVRE"],
}


def validate_plan(
    source: str | Path | NetcadParseResult | NetcadReader,
    plan_type: str | None = None,
) -> PlanValidationReport:
    """Validate a Netcad drawing for PlanGML and e-Plan compliance.

    Args:
        source: File path (str/Path), parsed NetcadParseResult, or NetcadReader instance.
        plan_type: Optional override ('UIP', 'NIP', 'CDP'). If None, detected from layers/source.

    Returns:
        PlanValidationReport with score, issues, land-use metrics, and missing requirements.
    """
    if isinstance(source, (str, Path)):
        path = Path(source)
        reader = NetcadReader(path).index()
        parse_res = reader.parse()
    elif isinstance(source, NetcadReader):
        reader = source
        reader.index()
        parse_res = reader.parse()
    elif isinstance(source, NetcadParseResult):
        parse_res = source
    else:
        raise TypeError(f"Unsupported source type: {type(source)}")

    # Detect or normalize plan type
    resolved_plan_type = plan_type
    if not resolved_plan_type:
        for name in parse_res.layer_names:
            detected = detect_plan_type(name)
            if detected:
                resolved_plan_type = detected
                break
    resolved_plan_type = resolved_plan_type or "UIP"

    issues: list[PlanValidationIssue] = []
    layer_names = list(parse_res.layer_names)
    total_layers = len(layer_names)
    matched_count = 0
    unmatched_layers: list[str] = []
    land_use_breakdown: dict[str, int] = {}

    classifications: dict[str, LayerClassification] = {}
    for lname in layer_names:
        c = classify_layer(lname, plan_type=resolved_plan_type)
        classifications[lname] = c
        if c.matched:
            matched_count += 1
            group_name = (
                c.identity.ust_grup_adi
                if c.identity and c.identity.ust_grup_adi
                else (c.style.get("ust_grup", "DİĞER") if c.style else "DİĞER")
            )
            land_use_breakdown[group_name] = land_use_breakdown.get(group_name, 0)
        else:
            unmatched_layers.append(lname)
            issues.append(
                PlanValidationIssue(
                    severity="WARNING",
                    category="CLASSIFICATION",
                    layer_name=lname,
                    message=f"Layer '{lname}' could not be matched with standard PlanGML / e-Plan schema.",
                    code="UNMATCHED_LAYER",
                )
            )

    # Mandatory layer check
    req_patterns = MANDATORY_PLAN_LAYERS.get(resolved_plan_type, ["ONAMA_SINIRI"])
    mandatory_present: list[str] = []
    mandatory_missing: list[str] = []

    normalized_all = [normalize_layer_name(ln) for ln in layer_names]
    for pattern in req_patterns:
        found = any(pattern in norm for norm in normalized_all)
        if found:
            mandatory_present.append(pattern)
        else:
            mandatory_missing.append(pattern)
            issues.append(
                PlanValidationIssue(
                    severity="ERROR" if pattern == "ONAMA_SINIRI" else "WARNING",
                    category="MANDATORY_LAYER",
                    layer_name=pattern,
                    message=f"Mandatory {resolved_plan_type} layer concept '{pattern}' not found in drawing.",
                    code="MISSING_MANDATORY_LAYER",
                )
            )

    # Geometry integrity check
    total_entities = len(parse_res.entities)
    for entity in parse_res.entities:
        coords = entity.coordinates
        if not coords and entity.geometry_kind in ("LINE", "POLYLINE", "POLYGON"):
            issues.append(
                PlanValidationIssue(
                    severity="WARNING",
                    category="GEOMETRY",
                    layer_name=entity.layer_name,
                    message=f"Entity on layer '{entity.layer_name}' has empty coordinate list.",
                    code="EMPTY_GEOMETRY",
                )
            )
        elif entity.geometry_kind == "POLYGON" and len(coords) < 3:
            issues.append(
                PlanValidationIssue(
                    severity="ERROR",
                    category="GEOMETRY",
                    layer_name=entity.layer_name,
                    message=f"Polygon entity on layer '{entity.layer_name}' has fewer than 3 vertices.",
                    code="DEGENERATE_POLYGON",
                )
            )

        # Count entity per land use group
        c = classifications.get(entity.layer_name)
        if c and c.matched:
            group = (
                c.identity.ust_grup_adi
                if c.identity and c.identity.ust_grup_adi
                else (c.style.get("ust_grup", "DİĞER") if c.style else "DİĞER")
            )
            land_use_breakdown[group] = land_use_breakdown.get(group, 0) + 1

    # Quality score calculation (0 - 100)
    score = 100.0
    error_count = sum(1 for i in issues if i.severity == "ERROR")
    warning_count = sum(1 for i in issues if i.severity == "WARNING")
    score -= error_count * 20.0
    score -= warning_count * 5.0
    if total_layers > 0:
        match_ratio = matched_count / total_layers
        score = score * 0.5 + (match_ratio * 100.0) * 0.5
    score = max(0.0, min(100.0, score))

    return PlanValidationReport(
        plan_type=resolved_plan_type,
        total_layers=total_layers,
        matched_layers=matched_count,
        unmatched_layers=unmatched_layers,
        total_entities=total_entities,
        quality_score=score,
        issues=issues,
        land_use_breakdown=land_use_breakdown,
        mandatory_layers_present=mandatory_present,
        mandatory_layers_missing=mandatory_missing,
    )
