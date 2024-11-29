# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
class MediaserverApiHttpError(Exception):
    """Error received from server."""

    def __init__(self, server_name, http_response, vms_error_dict):
        url = http_response.url
        status_code = http_response.status_code
        content_length = len(http_response.content)
        error_message = (
            f"HTTP {status_code} {http_response.reason}: "
            f"{http_response.request_method} {url} request to {server_name} failed;\n"
            f"Mediaserver error json: {vms_error_dict};\n"
            f"Content length {content_length} bytes;"
            )
        if len(http_response.content) > 20000:
            partial_content = http_response.content[:500] + b' ... ' + http_response.content[-500:]
            error_message += f"Partial HTTP response:\n{partial_content}"
        else:
            error_message += f"Full HTTP response:\n{http_response.content}"
        super(MediaserverApiHttpError, self).__init__(self, error_message)
        self.http_status = status_code
        try:
            self.vms_error_code = int(vms_error_dict['error'])
        except KeyError:
            self.vms_error_code = None
        self.vms_error_id = vms_error_dict.get('errorId')
        self.vms_error_string = vms_error_dict.get('errorString')


class Unauthorized(MediaserverApiHttpError):
    pass


class Forbidden(MediaserverApiHttpError):
    pass


class OldSessionToken(Forbidden):
    pass


class NotFound(MediaserverApiHttpError):
    pass


class BadRequest(MediaserverApiHttpError):
    pass


class NonJsonResponse(MediaserverApiHttpError):
    pass


class NoContent(Exception):
    pass


class MediaserverApiConnectionError(Exception):

    def __init__(self, server_name, error):
        super().__init__(error)
        self.server_name = server_name


class MediaserverApiReadTimeout(MediaserverApiConnectionError):
    pass
