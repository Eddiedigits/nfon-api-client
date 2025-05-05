class NFONApiError(Exception):
    """Base exception for NFON API errors."""
    pass

class AuthHeaderError(NFONApiError):
    """Raised when the auth header cannot be created."""
    pass

class EndpointFormatError(NFONApiError):
    """Raised when endpoint formatting fails."""
    pass

class RequestFailed(NFONApiError):
    """Raised when an HTTP request fails."""
    pass
