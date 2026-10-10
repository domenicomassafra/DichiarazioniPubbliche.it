"""DP-304 technical schema-field inventory: deterministic, deny-by-default.

An inventory is *not* a legal retention decision or a public projection grant.
New SQL columns must be inventoried before the repository acceptance can pass.
"""

from __future__ import annotations

import ast
from contextlib import closing
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Mapping

from dichiarazioni_pubbliche.policy.privacy_policy import PRIVACY_POLICY_VERSION, DataClass
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime
from dichiarazioni_pubbliche import public_schema

INVENTORY_VERSION = "privacy-field-inventory-v1"
_TABLE_START = re.compile(r"\bCREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([a-z][a-z0-9_]*)\s*\(", re.I)
_COLUMN_START = re.compile(r"^\s{4}([a-z][a-z0-9_]*)\s+(.+)$", re.I)
_SQL_CONSTRAINTS = frozenset({"PRIMARY", "FOREIGN", "CONSTRAINT", "CHECK", "UNIQUE", "EXCLUDE", "LIKE"})
_PUBLIC_IDENTIFIERS = frozenset({"id", "source_id", "content_id", "person_id", "topic_id", "event_id", "claim_id", "finding_id"})
_SAFE_PUBLIC_TEXT = frozenset({"normalized_claim", "normalized_statement", "canonical_name"})
_SENSITIVE_FIELDS = frozenset({"sensitive_signature", "sensitivity_class", "sensitivity_flags", "sensitive_categories"})
_IDENTITY_FIELDS = frozenset({"submitter_contact", "contact_details", "email_address", "phone_number", "private_address", "home_address", "identity_document"})
_FREE_TEXT_PRIVATE = frozenset({"raw_text", "canonical_text", "private_text", "excerpt", "response_body", "request_body", "prompt", "note", "notes", "contact"})
ROOT = Path(__file__).resolve().parents[2]
_PUBLIC_SCHEMA_MIGRATION = ROOT / "db/migrations/20260926-add-public-schema-v1-contract.sql"
_RELATION_POLICY_MIGRATION = ROOT / "db/migrations/20260926-add-relation-approval-policy.sql"
_ACCOUNT_SOURCE = ROOT / "poc/dichiarazioni_pubbliche/public_account.py"

# These are the fields emitted by the optional stdlib public HTTP access logger.
# The entire request line is potentially identifying and can contain OAuth codes.
# Neither its default-off state nor this inventory authorizes its use in production.
_RUNTIME_LOG_FIELDS = {
    "public_api_http_access_optional": (
        "client_address", "request_line", "response_code", "response_size", "timestamp"
    ),
    "public_api_startup_stdout": ("api_version", "bind_address", "bind_port"),
}
_ACCOUNT_RETENTION = {
    "pending": "TECHNICAL_5_MINUTE_EXPIRY_REQUEST_TIME_PURGE",
    "sessions": "TECHNICAL_24_HOUR_EXPIRY_REQUEST_TIME_PURGE",
    "throttle": "TECHNICAL_MINUTE_WINDOW_REQUEST_TIME_PURGE",
    "users": "MEMBER_DELETION_PENDING_QUALIFIED_RETENTION_REVIEW",
}
_ACCOUNT_PURPOSE = {
    "pending": "OIDC_ANTI_CSRF_AND_PKCE_FLOW",
    "sessions": "ACCOUNT_SESSION_AND_CSRF_PROTECTION",
    "throttle": "PSEUDONYMOUS_LOGIN_ABUSE_CONTROL",
    "users": "ACCOUNT_MEMBERSHIP_AND_IDENTITY_DISPLAY",
}
_ACCOUNT_HTTP_HEADER_FIELDS = ("Location", "Set-Cookie")


class FieldInventoryError(ValueError):
    pass


def parse_schema_fields(schema: str) -> dict[str, tuple[str, ...]]:
    """Parse only canonical, unquoted four-space-column DDL; never guess on drift."""
    tables: dict[str, tuple[str, ...]] = {}
    lines = schema.splitlines()
    for i, line in enumerate(lines):
        match = _TABLE_START.search(line)
        if not match or line.lstrip().startswith("--"):
            continue
        table = match.group(1).lower()
        if table in tables:
            raise FieldInventoryError("PRIVACY_INVENTORY_DUPLICATE_TABLE")
        columns: list[str] = []
        finished = False
        for body in lines[i + 1:]:
            if body.startswith(");"):
                finished = True
                break
            if body.startswith("    --") or not body.strip() or body.strip().startswith(")"):
                continue
            if not body.startswith("    ") or body.startswith("        "):
                # continuation, nested constraints or expressions
                continue
            column_match = _COLUMN_START.match(body)
            if not column_match:
                raise FieldInventoryError(f"PRIVACY_INVENTORY_UNRECOGNIZED_DDL:{table}")
            field, rest = column_match.groups()
            if field.upper() in _SQL_CONSTRAINTS:
                continue
            # A column declaration always starts with a type token; expressions
            # and unexpected DDL do not acquire a default authorization.
            type_name = rest.split(None, 1)[0].lower().rstrip(",")
            if type_name not in {
                "text", "integer", "smallint", "bigint", "boolean", "numeric",
                "real", "double", "date", "timestamptz", "timestamp", "jsonb",
                "json", "uuid", "bytea", "inet", "cidr", "interval",
            } and not type_name.startswith(("varchar", "character", "text[", "integer[", "bigint[", "numeric(", "decimal(")):
                raise FieldInventoryError(f"PRIVACY_INVENTORY_UNRECOGNIZED_TYPE:{table}.{field}")
            if field in columns:
                raise FieldInventoryError(f"PRIVACY_INVENTORY_DUPLICATE_FIELD:{table}.{field}")
            columns.append(field)
        if not finished or not columns:
            raise FieldInventoryError(f"PRIVACY_INVENTORY_UNTERMINATED_TABLE:{table}")
        tables[table] = tuple(columns)
    if not tables:
        raise FieldInventoryError("PRIVACY_INVENTORY_NO_TABLES")
    return dict(sorted(tables.items()))


def classify_field(table: str, column: str) -> str:
    # Schema-name classifications cannot infer value-level traits. Ambiguous
    # payloads stay private, never assigned public safety by a name heuristic.
    if column in _IDENTITY_FIELDS or column.endswith(("_email", "_phone", "_contact")):
        return DataClass.HIGH_RISK_IDENTITY.value
    if column in _SENSITIVE_FIELDS:
        return DataClass.SENSITIVE_CANDIDATE.value
    if column in _PUBLIC_IDENTIFIERS:
        return DataClass.PUBLIC_CORE.value
    if column in _SAFE_PUBLIC_TEXT:
        return DataClass.PUBLIC_SAFE_TEXT.value
    if column in _FREE_TEXT_PRIVATE or column.endswith(("_body", "_note", "_notes", "_text")):
        return DataClass.OPERATIONAL_PRIVATE.value
    return DataClass.OPERATIONAL_PRIVATE.value


def parse_sqlite_account_fields(python_source: str) -> dict[str, tuple[str, ...]]:
    """Extract AccountStore's literal SQLite DDL without executing account code."""
    try:
        module = ast.parse(python_source)
    except SyntaxError as exc:
        raise FieldInventoryError("PRIVACY_ACCOUNT_SOURCE_INVALID") from exc
    ddl: list[str] = []
    for node in ast.walk(module):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr == "executescript":
            if len(node.args) != 1 or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
                raise FieldInventoryError("PRIVACY_ACCOUNT_DYNAMIC_DDL_UNREVIEWED")
            ddl.append(node.args[0].value)
    if len(ddl) != 1:
        raise FieldInventoryError("PRIVACY_ACCOUNT_SCHEMA_SOURCE_DRIFT")
    raw = ddl[0]
    starts = tuple(re.finditer(r"\bCREATE\s+TABLE\b", raw, re.I))
    matches = tuple(re.finditer(
        r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([a-z][a-z0-9_]*)\s*\((.*?)\)\s*;",
        raw, re.I | re.S,
    ))
    if not starts or len(starts) != len(matches):
        raise FieldInventoryError("PRIVACY_ACCOUNT_UNRECOGNIZED_DDL")
    tables: dict[str, tuple[str, ...]] = {}
    for match in matches:
        table = match.group(1).lower()
        columns: list[str] = []
        for declaration in match.group(2).split(","):
            item = re.fullmatch(r"\s*([a-z][a-z0-9_]*)\s+(TEXT|INTEGER|REAL|BLOB|NUMERIC)\b[^,]*", declaration, re.I | re.S)
            if not item:
                raise FieldInventoryError(f"PRIVACY_ACCOUNT_COLUMN_UNRECOGNIZED:{table}")
            column = item.group(1).lower()
            if column in columns:
                raise FieldInventoryError(f"PRIVACY_ACCOUNT_DUPLICATE_COLUMN:{table}.{column}")
            columns.append(column)
        if not columns or table in tables:
            raise FieldInventoryError(f"PRIVACY_ACCOUNT_DUPLICATE_OR_EMPTY_TABLE:{table}")
        tables[table] = tuple(columns)
    if set(tables) != set(_ACCOUNT_RETENTION):
        raise FieldInventoryError("PRIVACY_ACCOUNT_UNREVIEWED_TABLE")
    return dict(sorted(tables.items()))


def account_sqlite_field_inventory(python_source: str) -> dict[str, dict[str, dict[str, str]]]:
    tables = parse_sqlite_account_fields(python_source)
    return {
        table: {
            column: {
                "schema_origin": "OPT_IN_ACCOUNTSTORE_SQLITE_DDL",
                "data_class": (
                    DataClass.HIGH_RISK_IDENTITY.value
                    if (table, column) in {("users", "subject"), ("users", "email"), ("throttle", "bucket")}
                    else DataClass.OPERATIONAL_PRIVATE.value
                ),
                "purpose": _ACCOUNT_PURPOSE[table],
                "access_role": "ACCOUNT_PRIVATE_SERVICE_ONLY",
                "retention_behavior": _ACCOUNT_RETENTION[table],
                "public_allowlist_decision": "DENY_ACCOUNT_STORE_PUBLIC_PROJECTION",
            }
            for column in columns
        }
        for table, columns in tables.items()
    }


def account_response_field_inventory(python_source: str) -> dict[str, dict[str, str]]:
    """Account response JSON keys are a separate, private user-specific projection."""
    try:
        module = ast.parse(python_source)
    except SyntaxError as exc:
        raise FieldInventoryError("PRIVACY_ACCOUNT_SOURCE_INVALID") from exc
    fields: set[str] = set()
    for node in ast.walk(module):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "_json":
            continue
        if len(node.args) != 2 or not isinstance(node.args[1], ast.Dict):
            raise FieldInventoryError("PRIVACY_ACCOUNT_DYNAMIC_RESPONSE_UNREVIEWED")
        for key in node.args[1].keys:
            if not isinstance(key, ast.Constant) or not isinstance(key.value, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", key.value):
                raise FieldInventoryError("PRIVACY_ACCOUNT_DYNAMIC_RESPONSE_FIELD")
            fields.add(key.value)
    if not fields:
        raise FieldInventoryError("PRIVACY_ACCOUNT_RESPONSE_FIELDS_MISSING")
    return {
        name: {
            "data_class": DataClass.HIGH_RISK_IDENTITY.value if name == "email" else DataClass.OPERATIONAL_PRIVATE.value,
            "purpose": "ACCOUNT_SELF_SERVICE_RESPONSE",
            "access_role": "ACCOUNT_SESSION_OWNER_OR_UNAUTHENTICATED_ERROR_ONLY",
            "retention_behavior": "EPHEMERAL_HTTP_NO_STORE_PRIVATE_RESPONSE",
            "public_allowlist_decision": "DENY_SHARED_PUBLIC_PROJECTION",
        }
        for name in sorted(fields)
    }


def read_account_sqlite_columns(path: Path) -> tuple[tuple[str, str], ...]:
    """Opt-in catalog read-back; opens SQLite read-only and never selects user rows."""
    db_path = Path(path)
    if db_path.is_symlink() or not db_path.is_file():
        raise FieldInventoryError("PRIVACY_ACCOUNT_DB_MISSING_OR_SYMLINK")
    if db_path.stat().st_mode & 0o077:
        raise FieldInventoryError("PRIVACY_ACCOUNT_DB_PERMISSIONS")
    try:
        with closing(sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            tables = [row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )]
            if not tables or any(not re.fullmatch(r"[a-z][a-z0-9_]*", name) for name in tables):
                raise FieldInventoryError("PRIVACY_ACCOUNT_LIVE_UNEXPECTED_TABLE")
            fields = [(table, row[1]) for table in tables for row in db.execute(f"PRAGMA table_info('{table}')")]
    except sqlite3.DatabaseError as exc:
        raise FieldInventoryError("PRIVACY_ACCOUNT_LIVE_CATALOG_FAILED") from exc
    if len(set(fields)) != len(fields) or not fields:
        raise FieldInventoryError("PRIVACY_ACCOUNT_LIVE_DUPLICATE_OR_EMPTY")
    return tuple(fields)


def compare_account_sqlite_columns(inventory: Mapping[str, Any], actual: tuple[tuple[str, str], ...]) -> dict[str, Any]:
    expected = {(table, col) for table, cols in inventory["account_sqlite_fields"].items() for col in cols}
    rows = set(actual)
    matching = len(rows) == len(actual) and expected == rows
    return {
        "status": "ACCOUNT_SQLITE_CATALOG_MATCH_TECHNICAL_ONLY" if matching else "ACCOUNT_SQLITE_SCHEMA_DRIFT_BLOCKED",
        "expected_fields": len(expected), "live_fields": len(actual),
        "unclassified_live_fields": len(rows - expected),
        "missing_from_live": len(expected - rows),
        "live_matches_inventory": matching,
        "public_projection_authorized": False,
    }


def make_inventory(schema: str) -> dict[str, Any]:
    tables = parse_schema_fields(schema)
    # Production includes two historical migration-only additions not folded
    # into the canonical DDL. Inventory the *effective* persisted schema rather
    # than claiming the base DDL alone covers every live PostgreSQL column.
    registry = parse_schema_fields(_PUBLIC_SCHEMA_MIGRATION.read_text(encoding="utf-8"))
    if set(registry) != {"public_schema_contract"} or "public_schema_contract" in tables:
        raise FieldInventoryError("PRIVACY_LEGACY_SCHEMA_REGISTRY_DRIFT")
    relation_sql = _RELATION_POLICY_MIGRATION.read_text(encoding="utf-8")
    if not re.search(
        r"ALTER\s+TABLE\s+claim_relation_candidate\s+ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+policy_version\s+text\b",
        relation_sql, re.I,
    ):
        raise FieldInventoryError("PRIVACY_LEGACY_RELATION_POLICY_COLUMN_DRIFT")
    if "claim_relation_candidate" not in tables or "policy_version" in tables["claim_relation_candidate"]:
        raise FieldInventoryError("PRIVACY_LEGACY_RELATION_POLICY_SCOPE_DRIFT")
    tables["public_schema_contract"] = registry["public_schema_contract"]
    tables["claim_relation_candidate"] = (*tables["claim_relation_candidate"], "policy_version")
    records: dict[str, dict[str, dict[str, str]]] = {}
    for table, columns in tables.items():
        fields = {}
        for column in columns:
            fields[column] = {
                "schema_origin": (
                    "20260926_PUBLIC_SCHEMA_CONTRACT_MIGRATION"
                    if table == "public_schema_contract"
                    else "20260926_RELATION_POLICY_MIGRATION"
                    if table == "claim_relation_candidate" and column == "policy_version"
                    else "CANONICAL_SCHEMA_V1"
                ),
                "data_class": classify_field(table, column),
                "purpose": "PERSISTED_PRODUCT_OPERATION_AND_PROVENANCE",
                "access_role": "AUTHENTICATED_PRIVATE_OPERATOR",
                "retention_behavior": "NO_UNAPPROVED_AUTOMATIC_DELETION",
                "public_allowlist_decision": "DENY_DIRECT_DB_PROJECTION",
            }
        records[table] = fields
    projection_groups = {
        group: {
            name: {
                "data_class": (
                    DataClass.PUBLIC_SAFE_TEXT.value
                    if name in {"claim", "canonical_name", "scope_text", "normalized_claim"}
                    else DataClass.PUBLIC_CORE.value
                ),
                "purpose": "REVIEWED_PUBLIC_SCHEMA_CONTRACT",
                "access_role": "PUBLIC_ONLY_AFTER_PUBLICATION_APPROVAL",
                "retention_behavior": "REVIEWED_PUBLIC_VERSION_HISTORY",
                "public_allowlist_decision": "CONDITIONAL_VIA_PUBLIC_SCHEMA_AND_REVIEW",
            }
            for name in sorted(keys)
        }
        for group, keys in sorted(vars(public_schema).items())
        if group.endswith("_ALLOWED_KEYS")
        and isinstance(keys, frozenset)
        and all(isinstance(name, str) for name in keys)
    }
    if len(projection_groups) < 10:
        raise FieldInventoryError("PRIVACY_PUBLIC_SCHEMA_GROUPS_MISSING")
    account_source = _ACCOUNT_SOURCE.read_text(encoding="utf-8")
    account_fields = account_sqlite_field_inventory(account_source)
    account_response_fields = account_response_field_inventory(account_source)
    runtime_logs = {
        group: {
            field: {
                "data_class": DataClass.OPERATIONAL_PRIVATE.value,
                "purpose": "OPTIONAL_PUBLIC_HOST_DIAGNOSTICS",
                "access_role": "AUTHORIZED_RUNTIME_OPERATOR_ONLY",
                "retention_behavior": "HOST_JOURNAL_OR_LOG_POLICY_PENDING_OWNER_REVIEW",
                "public_allowlist_decision": "DENY_PUBLIC_PROJECTION",
            }
            for field in fields
        }
        for group, fields in _RUNTIME_LOG_FIELDS.items()
    }
    return {
        "version": INVENTORY_VERSION,
        "privacy_policy_version": PRIVACY_POLICY_VERSION,
        "status": "TECHNICAL_CLASSIFICATION_NOT_LEGAL_APPROVAL",
        "public_projection_authorized": False,
        "retention_periods_approved": False,
        "runtime_log_retention_approved": False,
        "account_sqlite_activation_approved": False,
        "inventory_scope": "POSTGRESQL_COLUMNS_PUBLIC_SCHEMA_OPT_IN_ACCOUNT_SQLITE_AND_SOURCE_OWNED_PUBLIC_HTTP_LOGS",
        "external_runtime_log_fields_verified": False,
        "external_runtime_log_review_required": ["systemd_journald", "reverse_proxy_access_and_error", "provider_and_backup_logs"],
        "fields": records,
        "public_projection_fields": projection_groups,
        "account_sqlite_fields": account_fields,
        "account_http_response_fields": account_response_fields,
        "account_http_sensitive_headers": {
            name: {
                "data_class": DataClass.OPERATIONAL_PRIVATE.value,
                "purpose": "ACCOUNT_OIDC_REDIRECT_OR_SECURE_COOKIE",
                "access_role": "USER_BROWSER_AND_ACCOUNT_SERVICE_ONLY",
                "retention_behavior": (
                    "TECHNICAL_COOKIE_TTL_FLOW_5MIN_SESSION_24H_VISITOR_30D_PENDING_REVIEW"
                    if name == "Set-Cookie" else "NO_STORE_OIDC_REDIRECT_VALUE"
                ),
                "public_allowlist_decision": "DENY_SHARED_PUBLIC_PROJECTION",
            }
            for name in _ACCOUNT_HTTP_HEADER_FIELDS
        },
        "runtime_log_fields": runtime_logs,
    }


def canonical_inventory(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def check_inventory(schema_path: Path, inventory_path: Path) -> dict[str, int | str]:
    expected = make_inventory(schema_path.read_text(encoding="utf-8"))
    try:
        actual = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise FieldInventoryError("PRIVACY_INVENTORY_MISSING_OR_MALFORMED") from exc
    if actual != expected:
        raise FieldInventoryError("PRIVACY_INVENTORY_SCHEMA_OR_POLICY_DRIFT")
    canonical = canonical_inventory(expected)
    if inventory_path.read_text(encoding="utf-8") != canonical:
        raise FieldInventoryError("PRIVACY_INVENTORY_NOT_CANONICAL")
    return {
        "table_count": len(expected["fields"]),
        "field_count": sum(len(v) for v in expected["fields"].values()),
        "public_schema_field_count": sum(len(v) for v in expected["public_projection_fields"].values()),
        "public_schema_group_count": len(expected["public_projection_fields"]),
        "account_sqlite_table_count": len(expected["account_sqlite_fields"]),
        "account_sqlite_field_count": sum(len(v) for v in expected["account_sqlite_fields"].values()),
        "account_http_response_field_count": len(expected["account_http_response_fields"]),
        "runtime_log_field_count": sum(len(v) for v in expected["runtime_log_fields"].values()),
        "inventory_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "status": "TECHNICAL_ONLY_NOT_LEGAL_CLOSURE",
    }


class LivePrivacyFieldStore(PsqlRuntime):
    def read_columns(self) -> tuple[tuple[str, str], ...]:
        """Metadata-only, explicitly read-only SQL; no table data or private values."""
        raw = self.run(
            """
            BEGIN READ ONLY;
            SELECT cols.table_name || E'\t' || cols.column_name
            FROM information_schema.columns cols
            JOIN information_schema.tables tbl
              ON tbl.table_schema=cols.table_schema
             AND tbl.table_name=cols.table_name
            WHERE cols.table_schema=current_schema()
              AND tbl.table_type='BASE TABLE'
            ORDER BY cols.table_name, cols.ordinal_position;
            ROLLBACK;
            """
        )
        result: list[tuple[str, str]] = []
        for line in raw.splitlines():
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) != 2 or any(not re.fullmatch(r"[a-z][a-z0-9_]*", part) for part in parts):
                raise FieldInventoryError("PRIVACY_LIVE_CATALOG_UNEXPECTED_IDENTIFIER")
            result.append((parts[0], parts[1]))
        if not result or len(result) > 20_000 or len(set(result)) != len(result):
            raise FieldInventoryError("PRIVACY_LIVE_CATALOG_EMPTY_DUPLICATE_OR_OVERSIZE")
        return tuple(result)


def compare_live_columns(
    inventory: Mapping[str, Any], live_columns: tuple[tuple[str, str], ...]
) -> dict[str, int | bool | str]:
    fields = inventory.get("fields")
    if not isinstance(fields, Mapping) or not fields:
        raise FieldInventoryError("PRIVACY_INVENTORY_MISSING_FIELD_MAP")
    expected = {(table, name) for table, rows in fields.items() for name in rows}
    actual = set(live_columns)
    if len(actual) != len(live_columns):
        raise FieldInventoryError("PRIVACY_LIVE_CATALOG_DUPLICATE_COLUMN")
    missing = expected - actual
    unexpected = actual - expected
    return {
        "status": "SCHEMA_MATCH_TECHNICAL_ONLY" if not missing and not unexpected else "SCHEMA_DRIFT_BLOCKED",
        "expected_fields": len(expected),
        "live_fields": len(actual),
        "missing_from_live": len(missing),
        "unclassified_live_fields": len(unexpected),
        "live_matches_inventory": not missing and not unexpected,
        "public_projection_authorized": False,
        "retention_periods_approved": False,
    }
