from enum import StrEnum


class ProtocolStatus(StrEnum):
    SUCCESS = "success"
    RUNNING = "running"
    ACTION_CHUNK = "action_chunk"
    PARTIAL = "partial"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    INVALID_REQUEST = "invalid_request"
    INVALID_OUTPUT = "invalid_output"
    UNAVAILABLE = "unavailable"
    UNSAFE_OUTPUT = "unsafe_output"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    INTERNAL_ERROR = "internal_error"


TERMINAL_STATUSES = {
    ProtocolStatus.SUCCESS,
    ProtocolStatus.FAILURE,
    ProtocolStatus.CANCELLED,
    ProtocolStatus.TIMEOUT,
    ProtocolStatus.INVALID_REQUEST,
    ProtocolStatus.INVALID_OUTPUT,
    ProtocolStatus.UNAVAILABLE,
    ProtocolStatus.UNSAFE_OUTPUT,
    ProtocolStatus.RESOURCE_EXHAUSTED,
    ProtocolStatus.INTERNAL_ERROR,
}
