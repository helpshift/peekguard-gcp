import re
import time
from collections import defaultdict

import pyap
from fastapi import HTTPException
from presidio_analyzer import AnalyzerEngine, RecognizerResult

from peekguard.utils.alerts import send_alert
from peekguard.utils.logger import get_logger
from peekguard.utils.entities import PRESIDIO_ENTITIES


PLACEHOLDER_REGEX = r"<([A-Z0-9_]+)_(\d+)>"
MIN_THRESHOLD=0.6

logger = get_logger(__name__)


class PlaceholderManager:
    """Keeps the bi‑directional mapping: ``(entity, value) ⇄ placeholder``."""

    def __init__(self, existing: dict[str, str] | None) -> None:
        self._placeholder_to_pii: dict[str, str] = dict(existing or {})
        self._pii_to_placeholder: dict[tuple[str, str], str] = {}
        self._entity_counters: dict[str, int] = defaultdict(int)

        self._placeholder_re = re.compile(PLACEHOLDER_REGEX)
        self._initialise_from_existing()

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    def placeholder_for(self, entity: str, value: str) -> str:
        """Return the *deterministic* placeholder for an (entity, value) pair."""
        key = (entity, value)
        if key in self._pii_to_placeholder:
            return self._pii_to_placeholder[key]

        self._entity_counters[entity] += 1
        placeholder = f"<{entity}_{self._entity_counters[entity]}>"

        # Book‑keeping
        self._pii_to_placeholder[key] = placeholder
        self._placeholder_to_pii[placeholder] = value
        return placeholder

    @property
    def mappings(self) -> dict[str, str]:
        """Return **all** mappings (both old and newly created)."""
        return dict(self._placeholder_to_pii)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _initialise_from_existing(self) -> None:
        if not self._placeholder_to_pii:
            return

        for placeholder, original in self._placeholder_to_pii.items():
            match = self._placeholder_re.fullmatch(placeholder)
            if not match:
                logger.warning(
                    "Malformed placeholder '%s' in existing mappings – skipped.",
                    placeholder,
                )
                continue

            entity, number_s = match.groups()
            number = int(number_s)
            self._entity_counters[entity] = max(self._entity_counters[entity], number)
            self._pii_to_placeholder[(entity, original)] = placeholder


###############################################################################
# Masking engines
###############################################################################


class AddressMasker:
    """Detect and replace US addresses using *pyap* (more accurate than Presidio)."""

    def __init__(self, placeholder_mgr: PlaceholderManager):
        self._pm = placeholder_mgr

    def mask(self, text: str) -> tuple[str, list[tuple[int, int]]]:
        """Return (masked_text, spans_of_inserted_placeholders)."""
        replacements = []
        for addr in pyap.parse(text, country="US"):
            placeholder = self._pm.placeholder_for("LOCATION", addr.full_address)
            replacements.append(
                {
                    "start": addr.match_start,
                    "end": addr.match_end,
                    "placeholder": placeholder,
                }
            )

        # Apply replacements left→right while adjusting offsets
        replacements.sort(key=lambda r: r["start"])
        offset = 0
        masked = text
        spans: list[tuple[int, int]] = []
        for rep in replacements:
            start = rep["start"] + offset
            end = rep["end"] + offset
            masked = masked[:start] + rep["placeholder"] + masked[end:]
            offset += len(rep["placeholder"]) - (rep["end"] - rep["start"])
            spans.append((start, start + len(rep["placeholder"])))

        return masked, spans


class PresidioMasker:
    """Detect and replace all *remaining* entities with Microsoft Presidio."""

    def __init__(
        self,
        analyzer: AnalyzerEngine,
        placeholder_mgr: PlaceholderManager,
        language: str,
    ) -> None:
        self.analyzer = analyzer
        self._pm = placeholder_mgr
        self.language = language

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def mask(
        self,
        text: str,
        entities: list[str],
        exclude_spans: list[tuple[int, int]],
    ) -> str:
        """Mask *entities* that do **not** overlap *exclude_spans*."""
        if not entities:
            return text

        results: list[RecognizerResult] = self.analyzer.analyze(
            text=text,
            language=self.language,
            entities=entities,
            score_threshold=MIN_THRESHOLD,
        )

        # Sort for greedy longest‑first selection per original impl.
        results.sort(key=lambda r: (r.start, -(r.end - r.start), -r.score))

        chosen: list[RecognizerResult] = []
        last_end = -1
        for res in results:
            if self._overlaps_any(res.start, res.end, exclude_spans):
                continue
            if text[res.start : res.end] in self._pm.mappings.keys():
                continue  # already a placeholder
            if res.start >= last_end:
                chosen.append(res)
                last_end = res.end

        # Replace in text while tracking offset shifts
        offset = 0
        masked = text
        for res in chosen:
            entity = res.entity_type
            s = res.start + offset
            e = res.end + offset
            original_val = masked[s:e]
            placeholder = self._pm.placeholder_for(entity, original_val)
            masked = masked[:s] + placeholder + masked[e:]
            offset += len(placeholder) - len(original_val)

        return masked

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _overlaps_any(s: int, e: int, spans: list[tuple[int, int]]) -> bool:
        return any(max(s, ss) < min(e, ee) for ss, ee in spans)


###############################################################################
# Public façade
###############################################################################


def mask_sentence(
    sentence: str,
    analyzer: AnalyzerEngine | None,
    language: str,
    presidio_entities: list[str] | None,
    existing_mappings: dict[str, str] | None,
) -> tuple[str, dict[str, str]]:
    """Mask PII in *sentence* and return (masked_sentence, placeholder→PII map)."""
    start_t = time.time()

    # Check if presidio entities are provided and values are in PRESIDIO_ENTITIES
    if presidio_entities:
        invalid_entities = [
            entity for entity in presidio_entities if entity not in PRESIDIO_ENTITIES
        ]
        if invalid_entities:
            logger.warning(
                "Invalid Presidio entities provided: %s. Using default entities instead.",
                invalid_entities,
            )
            send_alert(
                status="critical",
                name="peekguard_mask_api_failed",
                message=f"Invalid Presidio entities: {invalid_entities}",
            )
            raise HTTPException(
                status_code=422,
                detail=f"Invalid Presidio entities: {invalid_entities}."
            )

    if not sentence:
        return "", {}

    # ------------------------------------------------------------------
    # 1. Setup helpers
    # ------------------------------------------------------------------
    pm = PlaceholderManager(existing_mappings)

    effective_entities = (
        list(presidio_entities)
        if presidio_entities
        else list(PRESIDIO_ENTITIES)
    )

    # ------------------------------------------------------------------
    # 2. First pass – addresses via pyap
    # ------------------------------------------------------------------
    address_spans: list[tuple[int, int]] = []
    current_text = sentence
    if "LOCATION" in effective_entities:
        address_start = time.time()
        current_text, address_spans = AddressMasker(pm).mask(sentence)
        logger.info("pyap address detection took %.4fs", time.time() - address_start)
        if address_spans:
            logger.info("pyap found and masked %d addresses.", len(address_spans))
            effective_entities.remove("LOCATION")
        else:
            logger.info(
                "pyap found no addresses. Presidio will handle LOCATION entity."
            )

    # ------------------------------------------------------------------
    # 3. Second pass – remaining entities via Presidio
    # ------------------------------------------------------------------
    if analyzer and effective_entities:
        presidio_start = time.time()
        current_text = PresidioMasker(analyzer, pm, language).mask(
            text=current_text,
            entities=effective_entities,
            exclude_spans=address_spans,
        )
        logger.info(
            "Presidio masking (entities=%s) took %.4fs",
            effective_entities,
            time.time() - presidio_start,
        )
    elif not analyzer and effective_entities:
        logger.warning("AnalyzerEngine is None – skipping Presidio masking step.")

    logger.info(
        "mask_sentence finished in %.4fs – generated %d new mappings (total %d)",
        time.time() - start_t,
        len(pm.mappings) - len(existing_mappings or {}),
        len(pm.mappings),
    )
    return current_text, pm.mappings
