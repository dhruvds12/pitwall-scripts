"""
Domain-specific exceptions for OpenF1 operations.
"""


class OpenF1Error(Exception):
    """Base exception class for OpenF1 operations."""
    pass


class SessionNotFoundError(OpenF1Error):
    """Raised when a requested session cannot be found."""
    pass


class SessionCancelledError(OpenF1Error):
    """Raised when a requested session was cancelled."""
    pass


class DriverNotFoundError(OpenF1Error):
    """Raised when a driver cannot be found in a session."""
    pass
