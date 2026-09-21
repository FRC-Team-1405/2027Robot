"""
WPILog binary parser -- compatibility shim.

The implementation moved to tools/wpilog-utils (package `wpilog_utils`) so that logbench,
wpilog-janitor and this tool share one copy; see docs/wpilog-janitor-plan.md. This module only
re-exports the original names (including the private ones other modules import) so existing
callers keep working. New code should import `wpilog_utils` directly.
"""
from wpilog_utils.decode import (  # noqa: F401
    decode_payload as _decode,
    handle_control as _handle_control,
    _lp_str,
    _warned_unknown_types,
    parse_wpilog,
    parse_wpilog_bytes as _parse_wpilog_bytes,
)
from wpilog_utils.records import (  # noqa: F401
    TRUNCATION_WARN_BYTES as _TRUNCATION_WARN_BYTES,
    build_record as _build_record,
    iter_records as _iter_records,
    warn_early_stop as _warn_early_stop,
    wpilog_header_end as _wpilog_header_end,
)
from wpilog_utils.trim import trim_wpilog_bytes  # noqa: F401
