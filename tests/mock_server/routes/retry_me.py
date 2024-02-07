import http
import random
import string

from urllib.parse import parse_qs

__failure_record = {}


def should_fail_by_times(success_times=None, failure_times=None):
    """
    Parameters
    ----------
    success_times: list[int], default=[1]
    failure_times: list[int], default=[0]

    Returns
    -------
    Generator[bool, None, None]

    Examples
    --------

    should_fail_by_times([2], [3])
        will succeed 2 times and failed 3 times, and loop

    should_fail_by_times([2, 4], [3])
        will succeed 2 times and failed 3 times,
        then succeeded 4 times and failed 3 time, and loop
    """
    if not success_times:
        success_times = [1]
    if not failure_times:
        failure_times = [0]

    def success_times_gen():
        while True:
            for i in success_times:
                yield i

    def failure_times_gen():
        while True:
            for i in failure_times:
                yield i

    success_times_iter = success_times_gen()
    fail_times_iter = failure_times_gen()

    while True:
        success = next(success_times_iter)
        fail = next(fail_times_iter)
        for _ in range(success):
            yield False
        for _ in range(fail):
            yield True


def handle_mgr_retry_me(method, parsed_uri, request_handler):
    """
    Parameters
    ----------
    method: str
        HTTP method
    parsed_uri: urllib.parse.ParseResult
        parsed URI
    request_handler: http.server.BaseHTTPRequestHandler
        request handler
    """
    if method not in ['PUT', 'DELETE']:
        request_handler.send_response(http.HTTPStatus.METHOD_NOT_ALLOWED)
        return
    match method:
        case 'PUT':
            # s for success
            success_times = parse_qs(parsed_uri.query).get('s', [])
            # f for failure
            failure_times = parse_qs(parsed_uri.query).get('f', [])

            record_id = ''.join(random.choices(string.ascii_letters, k=16))

            __failure_record[record_id] = should_fail_by_times(
                success_times=[int(n) for n in success_times],
                failure_times=[int(n) for n in failure_times]
            )

            request_handler.send_response(http.HTTPStatus.OK)
            request_handler.send_header('Content-Type', 'text/plain')
            request_handler.send_header('X-Reqid', record_id)
            request_handler.end_headers()

            request_handler.wfile.write(record_id.encode('utf-8'))
        case 'DELETE':
            record_id = parse_qs(parsed_uri.query).get('id')
            if not record_id or not record_id[0]:
                request_handler.send_response(http.HTTPStatus.BAD_REQUEST)
                return
            record_id = record_id[0]

            if record_id in __failure_record:
                del __failure_record[record_id]

            request_handler.send_response(http.HTTPStatus.NO_CONTENT)
            request_handler.send_header('X-Reqid', record_id)
            request_handler.end_headers()


def handle_retry_me(method, parsed_uri, request_handler):
    """
    Parameters
    ----------
    method: str
        HTTP method
    parsed_uri: urllib.parse.ParseResult
        parsed URI
    request_handler: http.server.BaseHTTPRequestHandler
        request handler
    """
    if method not in []:
        # all method allowed
        pass
    record_id = parse_qs(parsed_uri.query).get('id')
    if not record_id or not record_id[0]:
        request_handler.send_response(http.HTTPStatus.BAD_REQUEST)
        return
    record_id = record_id[0]

    should_fail = next(__failure_record[record_id])

    if should_fail:
        request_handler.send_response(-1)
        request_handler.send_header('Content-Type', 'text/plain')
        request_handler.send_header('X-Reqid', record_id)
        request_handler.end_headers()

        resp_body = 'service unavailable'
        request_handler.wfile.write(resp_body.encode('utf-8'))
        return

    request_handler.send_response(http.HTTPStatus.OK)
    request_handler.send_header('Content-Type', 'text/plain')
    request_handler.send_header('X-Reqid', record_id)
    request_handler.end_headers()

    resp_body = 'ok'
    request_handler.wfile.write(resp_body.encode('utf-8'))
