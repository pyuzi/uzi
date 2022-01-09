


class ObjectDoesNotExist(Exception):
    """The requested object does not exist"""
    silent_variable_failure = True


class MultipleObjectsReturned(Exception):
    """The query returned multiple objects when only one was expected."""
    pass


class SuspiciousOperation(Exception):
    """The user did something suspicious"""


class SuspiciousMultipartForm(SuspiciousOperation):
    """Suspect MIME request in multipart form data"""
    pass


class SuspiciousFileOperation(SuspiciousOperation):
    """A Suspicious filesystem operation was attempted"""
    pass


class DisallowedHost(SuspiciousOperation):
    """HTTP_HOST header contains invalid value"""
    pass


class DisallowedRedirect(SuspiciousOperation):
    """Redirect to scheme not in allowed list"""
    pass


class TooManyFieldsSent(SuspiciousOperation):
    """
    The number of fields in a GET or POST request exceeded
    settings.DATA_UPLOAD_MAX_NUMBER_FIELDS.
    """
    pass


class RequestDataTooBig(SuspiciousOperation):
    """
    The size of the request (excluding any file uploads) exceeded
    settings.DATA_UPLOAD_MAX_MEMORY_SIZE.
    """
    pass


class RequestAborted(Exception):
    """The request was closed before it was completed, or timed out."""
    pass


class BadRequest(Exception):
    """The request is malformed and cannot be processed."""
    pass


class PermissionDenied(Exception):
    """The user did not have permission to do that"""
    pass


try:
    from django.core import exceptions as dj_exc
except ImportError:
    pass
else:
    for k in list(globals()):
        v = globals()[k]
        if isinstance(v, type) and issubclass(v, Exception):
            globals()[k] = getattr(dj_exc, k, v)
