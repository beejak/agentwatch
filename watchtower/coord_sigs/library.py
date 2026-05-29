"""Coordination Signature Library — loads and matches failure patterns."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel

from watchtower.coord_sigs.matcher import match_signatures


class SignatureMatch(BaseModel):
    signature_id: str
    category: str       # "mast_spec","mast_alignment","mast_verify","aegis","infra"
    name: str
    risk_level: str     # "low","medium","high","critical"
    description: str
    fix_direction: str
    matched_agents: list[str]
    confidence: float

    @property
    def signature_name(self) -> str:
        """Alias for name — used in POC tests."""
        return self.name


class CoordSignatureLibrary:
    """Loads YAML signatures and matches them against live traces."""

    SIGNATURES_DIR = Path(__file__).parent / "signatures"

    def __init__(self) -> None:
        self._signatures: list[dict] = []
        self._loaded = False

    async def load(self) -> None:
        """Load all signature YAML files."""
        self._signatures = []
        self._signatures.extend(self._load_mast())
        self._signatures.extend(self._load_infra())
        self._loaded = True

    def _load_mast(self) -> list[dict]:
        path = self.SIGNATURES_DIR / "mast.yaml"
        if not path.exists():
            return []
        data = yaml.safe_load(path.read_text())
        sigs = []
        category_map = {
            "category_1_specification": "mast_spec",
            "category_2_inter_agent_misalignment": "mast_alignment",
            "category_3_verification_gaps": "mast_verify",
        }
        for cat_key, category in category_map.items():
            cat_data = data.get(cat_key, {})
            for sig in cat_data.get("signatures", []):
                sig["_category"] = category
                sigs.append(sig)
        return sigs

    def _load_infra(self) -> list[dict]:
        path = self.SIGNATURES_DIR / "infra.yaml"
        if not path.exists():
            return []
        data = yaml.safe_load(path.read_text())
        sigs = []
        for sig in data.get("infrastructure_patterns", []):
            sig["_category"] = "infra"
            sigs.append(sig)
        return sigs

    async def match_topology(self, spans: list) -> list[SignatureMatch]:
        """Match spans against all loaded signatures."""
        if not self._loaded:
            await self.load()

        raw_matches = match_signatures(spans, self._signatures)

        results = []
        for sig, confidence, matched_agents in raw_matches:
            results.append(SignatureMatch(
                signature_id=sig.get("id", "unknown"),
                category=sig.get("_category", "unknown"),
                name=sig.get("name", ""),
                risk_level=sig.get("risk_level", "medium"),
                description=sig.get("description", ""),
                fix_direction=sig.get("fix_direction", ""),
                matched_agents=matched_agents,
                confidence=confidence,
            ))

        # Sort by confidence descending
        results.sort(key=lambda m: m.confidence, reverse=True)
        return results

    def get_all_signatures(self) -> list[SignatureMatch]:
        """Return all loaded signatures as SignatureMatch objects (with empty matched_agents)."""
        result = []
        category_map = {
            "mast_spec": "mast_spec",
            "mast_alignment": "mast_alignment",
            "mast_verify": "mast_verify",
            "infra": "infra",
        }
        for sig in self._signatures:
            category = sig.get("_category", "unknown")
            result.append(SignatureMatch(
                signature_id=sig.get("id", "unknown"),
                category=category,
                name=sig.get("name", ""),
                risk_level=sig.get("risk_level", "medium"),
                description=sig.get("description", ""),
                fix_direction=sig.get("fix_direction", ""),
                matched_agents=[],
                confidence=0.0,
            ))
        return result

    @property
    def signature_count(self) -> int:
        return len(self._signatures)
