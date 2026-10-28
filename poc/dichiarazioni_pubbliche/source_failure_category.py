"""Safe, stable source-poll error categories for run and source receipts."""

import re

from dichiarazioni_pubbliche.source_adapters import SourceAdapterError


def classify_source_error(value: object) -> str:
    if isinstance(value, SourceAdapterError):
        return value.category
    if isinstance(value, TimeoutError):
        return "TIMEOUT"
    text = str(value or "").upper()
    relevance = re.search(r"INGESTION_[A-Z0-9_]+", text)
    if relevance is not None:
        return relevance.group(0)[:80]
    if any(marker in text for marker in ("DISCOVERY_URL", "NONPUBLIC_IP", "SSRF", "PRIVATE_IP")):
        return "SSRF_REJECTED"
    if any(marker in text for marker in ("PARSE", "XML", "MALFORMED", "FEED")):
        return "MALFORMED_RESPONSE"
    if "UNSUPPORTED" in text:
        return "UNSUPPORTED"
    if "BUDGET" in text or "COST" in text:
        return "BUDGET_BLOCKED"
    name = type(value).__name__ if isinstance(value, BaseException) else ""
    if "PARSE" in name.upper():
        return "MALFORMED_RESPONSE"
    category = re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")
    return category[:80] or "SOURCE_FAILURE"
