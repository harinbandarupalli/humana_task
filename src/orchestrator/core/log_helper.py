"""Contextual Structured Log Helper with PII Redaction, Timing, and State Buffering."""

import contextvars
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import logging
import re
import sys
import time
from typing import Any, Dict, Generator, List, Optional
try:
    from src.orchestrator.config.settings import settings
except ImportError:
    # Minimal fallback when running without pydantic_settings installed
    class _FallbackSettings:
        ENVIRONMENT = "development"
        LOG_LEVEL = "INFO"
    settings = _FallbackSettings()

# ============================================================================
# Context Variables for Distributed Execution Tracing
# ============================================================================
_current_order_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("current_order_id", default=None)
_current_node_name: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("current_node_name", default=None)
_current_user_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("current_user_id", default=None)
_current_stage_version: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar("current_stage_version", default=None)
_current_state_buffer: contextvars.ContextVar[Optional[List[str]]] = contextvars.ContextVar("current_state_buffer", default=None)


# ============================================================================
# PII & Secret Redaction Filter
# ============================================================================
class SecretRedactionFilter(logging.Filter):
    """
    High-performance compiled regex filter that sanitizes PII and credentials
    from log records before writing to stdout or aggregators.
    """

    PATTERNS = [
        # Bearer tokens / JWTs
        (re.compile(r'(?i)\b(bearer|token|apikey|key)\s+[A-Za-z0-9_\-\.]{15,}\b'), r'\1 [REDACTED_TOKEN]'),
        # Key-value secret parameters (password=..., secret=...)
        (re.compile(r'(?i)\b(api[_-]?key|secret|password|access[_-]?token)=([^\s&]+)\b'), r'\1=[REDACTED]'),
        # Credit Card Numbers (13 to 16 digits with optional dashes/spaces)
        (re.compile(r'\b(?:\d[ -]*?){13,16}\b'), r'[CARD_REDACTED]'),
        # Social Security / Tax ID
        (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), r'[SSN_REDACTED]'),
    ]

    SENSITIVE_DICT_KEYS = {
        "password", "secret", "token", "access_token", "api_key",
        "card_number", "cvv", "credit_card", "authorization"
    }

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.sanitize_string(record.msg)
        elif isinstance(record.msg, dict):
            record.msg = self.sanitize_dict(record.msg)

        if record.args:
            if isinstance(record.args, dict):
                record.args = self.sanitize_dict(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self.sanitize_string(arg) if isinstance(arg, str)
                    else (self.sanitize_dict(arg) if isinstance(arg, dict) else arg)
                    for arg in record.args
                )
        return True

    @classmethod
    def sanitize_string(cls, text: str) -> str:
        for pattern, replacement in cls.PATTERNS:
            text = pattern.sub(replacement, text)
        return text

    @classmethod
    def sanitize_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        sanitized = {}
        for k, v in data.items():
            if str(k).lower() in cls.SENSITIVE_DICT_KEYS:
                sanitized[k] = "[REDACTED]"
            elif isinstance(v, dict):
                sanitized[k] = cls.sanitize_dict(v)
            elif isinstance(v, str):
                sanitized[k] = cls.sanitize_string(v)
            else:
                sanitized[k] = v
        return sanitized


# ============================================================================
# Structured Formatters (Console & JSON)
# ============================================================================
class OrderConsoleFormatter(logging.Formatter):
    """Clean, contextual human-readable console formatter for development."""

    def format(self, record: logging.LogRecord) -> str:
        order_id = _current_order_id.get() or "-"
        node_name = _current_node_name.get() or "-"
        stage_version = _current_stage_version.get()
        v_str = f" (v{stage_version})" if stage_version else ""

        dt = datetime.fromtimestamp(record.created, timezone.utc)
        asctime = dt.strftime("%Y-%m-%d %H:%M:%S")
        levelname = record.levelname

        duration_ms = getattr(record, "duration_ms", None)
        dur_str = f" [{duration_ms}ms]" if duration_ms is not None else ""

        message = super().format(record)
        return f"{asctime} [{levelname:<5}] [{order_id}] [{node_name}{v_str}]{dur_str}: {message}"


class OrderJsonFormatter(logging.Formatter):
    """Single-line JSON structured log formatter for Datadog / CloudWatch / ELK."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "order_id": _current_order_id.get(),
            "node_name": _current_node_name.get(),
            "user_id": _current_user_id.get(),
            "stage_version": _current_stage_version.get(),
            "message": record.getMessage(),
        }

        if hasattr(record, "duration_ms"):
            payload["duration_ms"] = record.duration_ms

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload)


# ============================================================================
# Latency Profiling Helper
# ============================================================================
class TimedOperation:
    """Context manager to measure latency of node operations in milliseconds."""

    def __init__(self, operation_name: str, logger: logging.Logger):
        self.operation_name = operation_name
        self.logger = logger
        self.duration_ms: Optional[int] = None
        self._start_time: Optional[float] = None

    def __enter__(self):
        self._start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._start_time is not None:
            self.duration_ms = int((time.time() - self._start_time) * 1000)
            if exc_type is not None:
                self.logger.warning(
                    f"Operation '{self.operation_name}' failed after {self.duration_ms}ms: {exc_val}",
                    extra={"duration_ms": self.duration_ms},
                )
            else:
                self.logger.debug(
                    f"Operation '{self.operation_name}' completed in {self.duration_ms}ms.",
                    extra={"duration_ms": self.duration_ms},
                )


# ============================================================================
# Order Logger Adapter & Helpers
# ============================================================================
class OrderLoggerAdapter(logging.LoggerAdapter):
    """Adapter wrapping standard logging with timing and state buffering helpers."""

    def timed_operation(self, operation_name: str) -> TimedOperation:
        """Context manager to profile execution duration in milliseconds."""
        return TimedOperation(operation_name, self.logger)

    def _append_to_buffer(self, tagged_message: str) -> None:
        buf = _current_state_buffer.get()
        if buf is not None:
            buf.append(tagged_message)

    def append_state_info(self, message: str) -> None:
        """Emits an INFO log and appends '[INFO ] <msg>' to the LangGraph state buffer."""
        self.info(message)
        self._append_to_buffer(f"[INFO ] {message}")

    def append_state_warning(self, message: str) -> None:
        """Emits a WARNING log and appends '[WARN ] <msg>' to the LangGraph state buffer."""
        self.warning(message)
        self._append_to_buffer(f"[WARN ] {message}")

    def append_state_error(self, message: str) -> None:
        """Emits an ERROR log and appends '[ERROR] <msg>' to the LangGraph state buffer."""
        self.error(message)
        self._append_to_buffer(f"[ERROR] {message}")

    def append_state_log(self, message: str, level: str = "INFO") -> None:
        """Backward-compatible dynamic level state logger."""
        lvl = level.upper()
        if lvl in ("WARN", "WARNING"):
            self.append_state_warning(message)
        elif lvl == "ERROR":
            self.append_state_error(message)
        else:
            self.append_state_info(message)

    def get_buffered_logs(self) -> List[str]:
        """Returns collected logs for LangGraph state channel return."""
        buf = _current_state_buffer.get()
        return list(buf) if buf is not None else []


# ============================================================================
# Public Context Management & Setup Functions
# ============================================================================
@contextmanager
def order_log_context(
    order_id: str,
    node_name: str,
    user_id: Optional[str] = None,
    stage_version: Optional[int] = None,
) -> Generator[OrderLoggerAdapter, None, None]:
    """
    Context manager that binds order tracking variables to the current asynchronous execution context.
    Any logs emitted within this block will automatically carry order_id, node_name, and timing metadata.
    """
    t_order = _current_order_id.set(order_id)
    t_node = _current_node_name.set(node_name)
    t_user = _current_user_id.set(user_id)
    t_ver = _current_stage_version.set(stage_version)
    buffer: List[str] = []
    t_buf = _current_state_buffer.set(buffer)

    logger = get_order_logger("orchestrator")
    logger.debug(f"Entering node execution context [{node_name}] for order [{order_id}]")

    try:
        yield logger
    finally:
        _current_order_id.reset(t_order)
        _current_node_name.reset(t_node)
        _current_user_id.reset(t_user)
        _current_stage_version.reset(t_ver)
        _current_state_buffer.reset(t_buf)


def get_order_logger(name: str = "orchestrator") -> OrderLoggerAdapter:
    """Configures and returns a contextual order logger."""
    base_logger = logging.getLogger(name)

    if not base_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        redaction_filter = SecretRedactionFilter()
        handler.addFilter(redaction_filter)

        # Use JSON in production, human-readable in development
        if settings.ENVIRONMENT.lower() == "production":
            handler.setFormatter(OrderJsonFormatter())
        else:
            handler.setFormatter(OrderConsoleFormatter())

        base_logger.addHandler(handler)
        base_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
        base_logger.propagate = False

    return OrderLoggerAdapter(base_logger, extra={})


# Global convenience logger
order_logger = get_order_logger()
