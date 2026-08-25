"""PlanGML identity and e-Plan style matching for Netcad layers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .eplan_catalog import EPLAN_CATALOG, EPLAN_PLAN_TYPES
from .ncz_engine.model import NetcadEntity
from .plangml_schema import TabakaIdentity, lookup_tabaka

_TR_MAP = str.maketrans({
    "Ç": "C",
    "Ğ": "G",
    "I": "I",
    "İ": "I",
    "Ö": "O",
    "Ş": "S",
    "Ü": "U",
    "ç": "C",
    "ğ": "G",
    "ı": "I",
    "i": "I",
    "ö": "O",
    "ş": "S",
    "ü": "U",
})

_PLAN_TYPE_FALLBACK = {
    "UIP": ("UIP", "NIP", "CDP"),
    "NIP": ("NIP", "UIP", "CDP"),
    "CDP": ("CDP", "NIP", "UIP"),
}

_PLAN_TYPE_WORDS = {
    "UIP": "UIP",
    "UYGULAMA": "UIP",
    "MUIP": "UIP",
    "NIP": "NIP",
    "NAZIM": "NIP",
    "MNIP": "NIP",
    "CDP": "CDP",
    "CEVRE": "CDP",
}

_PLAN_TYPE_SCALES = {
    "500": "UIP",
    "1000": "UIP",
    "2000": "UIP",
    "5000": "NIP",
    "10000": "NIP",
    "25000": "CDP",
    "50000": "CDP",
    "100000": "CDP",
    "200000": "CDP",
}

_PREFIX_RE = re.compile(
    r"^(\d+[\._-]*)?(UIP_|NIP_|CDP_|MUIP_|MNIP_|KDP_|PL_|HAT_|KST_|PLAN_|NCZ_LAYER_|LAYER_)",
    re.IGNORECASE,
)
_SUFFIX_RE = re.compile(r"(_POLYGON|_LINESTRING|_LINE|_POINT|_TEXT|_TABLE)$", re.IGNORECASE)


@dataclass(frozen=True)
class LayerClassification:
    """Official PlanGML identity and e-Plan style data for one Netcad layer."""

    layer_name: str
    plan_type: str
    identity: TabakaIdentity | None
    style: dict[str, Any] | None
    style_key: str = ""
    style_plan_type: str = ""

    @property
    def matched(self) -> bool:
        return self.identity is not None or self.style is not None

    def to_dict(self) -> dict[str, Any]:
        identity = _identity_dict(self.identity)
        return {
            "layer_name": self.layer_name,
            "plan_type": self.plan_type,
            "matched": self.matched,
            "identity": identity,
            "style": self.style,
            "style_key": self.style_key,
            "style_plan_type": self.style_plan_type,
        }


def detect_plan_type(name: str | None) -> str | None:
    """Infer UIP/NIP/CDP from a file or layer name."""
    if not name:
        return None
    tokens = [token for token in normalize_layer_name(name, strip_known_prefixes=False).split("_") if token]
    for token in tokens:
        if token in _PLAN_TYPE_WORDS:
            return _PLAN_TYPE_WORDS[token]
    for token in tokens:
        if token in _PLAN_TYPE_SCALES:
            return _PLAN_TYPE_SCALES[token]
    return None


def normalize_layer_name(name: str | None, *, strip_known_prefixes: bool = True) -> str:
    """Normalize a Netcad layer name for catalog matching."""
    if not name:
        return ""
    text = str(name).strip().upper().translate(_TR_MAP)
    if strip_known_prefixes:
        previous = None
        while previous != text:
            previous = text
            text = _PREFIX_RE.sub("", text)
    text = _SUFFIX_RE.sub("", text)
    return re.sub(r"[^A-Z0-9]+", "_", text).strip("_")


def classify_entity(entity: NetcadEntity, plan_type: str = "UIP") -> LayerClassification:
    """Classify a Netcad entity by its layer name."""
    return classify_layer(entity.layer_name, plan_type=plan_type)


def classify_layers(layer_names: list[str], plan_type: str = "UIP") -> dict[str, LayerClassification]:
    """Classify unique layer names while preserving the requested plan type."""
    return {name: classify_layer(name, plan_type=plan_type) for name in dict.fromkeys(layer_names)}


def classify_layer(layer_name: str, plan_type: str = "UIP") -> LayerClassification:
    """Resolve official MPYY identity and e-Plan style metadata for a layer."""
    requested_plan_type = _clean_plan_type(plan_type) or detect_plan_type(layer_name) or "UIP"
    identity = lookup_tabaka(layer_name)
    style_key, style_plan_type, style = _find_style(layer_name, requested_plan_type, identity)
    return LayerClassification(
        layer_name=layer_name,
        plan_type=requested_plan_type,
        identity=identity,
        style=dict(style) if style else None,
        style_key=style_key,
        style_plan_type=style_plan_type,
    )


def classification_properties(classification: LayerClassification) -> dict[str, Any]:
    """Flatten classification data into stable GeoJSON properties."""
    identity = classification.identity
    style = classification.style or {}
    props: dict[str, Any] = {
        "plangml_plan_type": classification.plan_type,
        "plangml_matched": classification.matched,
        "plangml_tabaka": identity.tabaka if identity else "",
        "plangml_ust_grup_id": identity.ust_grup_id if identity else "",
        "plangml_ust_grup_adi": identity.ust_grup_adi if identity else "",
        "plangml_fonksiyon_kodu": identity.fonksiyon_kodu if identity else "",
        "plangml_fonksiyon_adi": identity.fonksiyon_adi if identity else "",
        "plangml_geometri": identity.geometri if identity else "",
        "plangml_match_type": identity.matched_as if identity else "",
        "eplan_style_key": classification.style_key,
        "eplan_style_plan_type": classification.style_plan_type,
    }
    for key, value in style.items():
        props[f"eplan_{key}"] = value
    return props


def _clean_plan_type(plan_type: str | None) -> str | None:
    if not plan_type:
        return None
    normalized = normalize_layer_name(plan_type, strip_known_prefixes=False)
    return normalized if normalized in EPLAN_PLAN_TYPES else None


def _find_style(
    layer_name: str,
    plan_type: str,
    identity: TabakaIdentity | None,
) -> tuple[str, str, dict[str, Any] | None]:
    for candidate in _style_candidates(layer_name, identity):
        for resolved_plan_type in _PLAN_TYPE_FALLBACK.get(plan_type, ("UIP", "NIP", "CDP")):
            entry = EPLAN_CATALOG.get(resolved_plan_type, {}).get(candidate)
            if entry:
                return candidate, resolved_plan_type, entry
    tokens = normalize_layer_name(layer_name).split("_")
    for key_tokens, key in _eplan_match_keys():
        if _contains_subsequence(tokens, key_tokens):
            for resolved_plan_type in _PLAN_TYPE_FALLBACK.get(plan_type, ("UIP", "NIP", "CDP")):
                entry = EPLAN_CATALOG.get(resolved_plan_type, {}).get(key)
                if entry:
                    return key, resolved_plan_type, entry
    return "", "", None


def _style_candidates(layer_name: str, identity: TabakaIdentity | None) -> list[str]:
    names = [layer_name]
    if identity:
        names.extend([identity.tabaka, identity.fonksiyon_adi])

    candidates: list[str] = []
    for name in names:
        normalized = normalize_layer_name(name)
        if normalized:
            candidates.append(normalized)
        raw = normalize_layer_name(name, strip_known_prefixes=False)
        if raw:
            candidates.append(raw)
            candidates.extend(_drop_prefixes(raw))
    return list(dict.fromkeys(candidates))


def _drop_prefixes(token: str) -> list[str]:
    parts = token.split("_")
    if len(parts) <= 1:
        return []
    dropped = []
    for prefix in ("PL", "HAT", "KST", "UIP", "NIP", "CDP", "MUIP", "MNIP", "KDP"):
        if parts[0] == prefix:
            dropped.append("_".join(parts[1:]))
    if parts[:2] == ["PL", "KONUT"]:
        dropped.append("_".join(parts[2:]))
    return [item for item in dropped if item]


def _eplan_match_keys() -> list[tuple[tuple[str, ...], str]]:
    cached = getattr(_eplan_match_keys, "_cache", None)
    if cached is None:
        keys = set()
        for entries in EPLAN_CATALOG.values():
            keys.update(entries)
        cached = sorted(
            ((tuple(key.split("_")), key) for key in keys),
            key=lambda item: (-len(item[0]), -len(item[1])),
        )
        _eplan_match_keys._cache = cached
    return cached


def _contains_subsequence(tokens: list[str], key_tokens: tuple[str, ...]) -> bool:
    if len(key_tokens) > len(tokens):
        return False
    for index in range(len(tokens) - len(key_tokens) + 1):
        if tuple(tokens[index:index + len(key_tokens)]) == key_tokens:
            return True
    return False


def _identity_dict(identity: TabakaIdentity | None) -> dict[str, str] | None:
    if identity is None:
        return None
    return {
        "tabaka": identity.tabaka,
        "ust_grup_id": identity.ust_grup_id,
        "ust_grup_adi": identity.ust_grup_adi,
        "fonksiyon_kodu": identity.fonksiyon_kodu,
        "fonksiyon_adi": identity.fonksiyon_adi,
        "geometri": identity.geometri,
        "matched_as": identity.matched_as,
    }
