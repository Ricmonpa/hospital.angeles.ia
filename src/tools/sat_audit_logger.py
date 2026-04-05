"""OpenDoc - SAT Portal Audit Logger.

Dedicated module for audit trail logging of SAT portal navigation.
Every action taken on the SAT portal is recorded with timestamps,
screenshots, and structured JSON for full traceability.

This ensures accountability and transparency — if anything ever
needs to be reviewed, the complete history is available.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

DEFAULT_AUDIT_DIR = "/app/data/sat_audit"


def _ensure_dir(path: str) -> Path:
    """Ensure directory exists."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_audit_logger(
    rfc: str,
    session_id: Optional[str] = None,
    audit_dir: str = DEFAULT_AUDIT_DIR,
) -> logging.Logger:
    """Create a file logger for a specific SAT navigation session.

    Each session gets its own log file with structured JSON entries.

    Args:
        rfc: The RFC being accessed
        session_id: Optional unique session ID (auto-generated if None)
        audit_dir: Directory for audit log files

    Returns:
        Configured logging.Logger instance
    """
    _ensure_dir(audit_dir)

    if not session_id:
        date_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        session_id = f"{rfc}_{date_str}"

    logger_name = f"sat_audit_{session_id}"
    logger = logging.getLogger(logger_name)

    # Avoid duplicate handlers
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        # File handler — JSON lines format
        log_file = Path(audit_dir) / f"{session_id}.jsonl"
        fh = logging.FileHandler(str(log_file), encoding="utf-8")
        fh.setLevel(logging.INFO)

        # Custom formatter for JSON lines
        formatter = logging.Formatter("%(message)s")
        fh.setFormatter(formatter)

        logger.addHandler(fh)

    return logger


def log_navigation_step(
    logger: logging.Logger,
    step,
) -> None:
    """Log a single navigation step as structured JSON line.

    Args:
        logger: The audit logger instance
        step: SATNavigationStep instance (or any object with to_dict())
    """
    entry = {
        "event": "navigation_step",
        "logged_at": datetime.now().isoformat(),
    }

    if hasattr(step, "to_dict"):
        entry["step"] = step.to_dict()
    elif isinstance(step, dict):
        entry["step"] = step
    else:
        entry["step"] = str(step)

    logger.info(json.dumps(entry, ensure_ascii=False, default=str))


def log_session_summary(
    logger: logging.Logger,
    result,
) -> None:
    """Log the complete session summary at the end.

    Args:
        logger: The audit logger instance
        result: SATPortalResult instance (or any object with to_dict())
    """
    entry = {
        "event": "session_summary",
        "logged_at": datetime.now().isoformat(),
    }

    if hasattr(result, "to_dict"):
        entry["result"] = result.to_dict()
    elif isinstance(result, dict):
        entry["result"] = result
    else:
        entry["result"] = str(result)

    logger.info(json.dumps(entry, ensure_ascii=False, default=str))


def export_audit_trail(
    session,
    audit_dir: str = DEFAULT_AUDIT_DIR,
) -> str:
    """Export the complete audit trail as a JSON file.

    Creates a standalone JSON file with all navigation steps,
    timestamps, and session metadata for review.

    Args:
        session: SATSession instance with navigation_log
        audit_dir: Directory for audit exports

    Returns:
        Path to the exported JSON file.
    """
    _ensure_dir(audit_dir)

    date_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    rfc = session.rfc if hasattr(session, "rfc") else "unknown"
    export_filename = f"{rfc}_{date_str}_audit_export.json"
    export_path = str(Path(audit_dir) / export_filename)

    # Build export data
    export_data = {
        "export_timestamp": datetime.now().isoformat(),
        "rfc": rfc,
        "total_steps": 0,
        "steps": [],
    }

    if hasattr(session, "to_dict"):
        export_data["session"] = session.to_dict()
    if hasattr(session, "navigation_log"):
        steps = session.navigation_log
        export_data["total_steps"] = len(steps)
        for step in steps:
            if hasattr(step, "to_dict"):
                export_data["steps"].append(step.to_dict())
            elif isinstance(step, dict):
                export_data["steps"].append(step)
            else:
                export_data["steps"].append(str(step))

    with open(export_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)

    return export_path
