import http
import logging
import time

from urllib.parse import parse_qs


def handle_timeout(method, parsed_uri, request_handler):
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
    delay = parse_qs(parsed_uri.query).get('delay')
    if not delay:
        delay = 3
        logging.info('No delay specified. Fallback to %s seconds.', delay)
    else:
        delay = float(delay[0])

    time.sleep(delay)
    request_handler.send_response(http.HTTPStatus.OK)
    request_handler.send_header('Content-Type', 'text/plain')
    request_handler.send_header('X-Reqid', 'mocked-req-id')
    request_handler.end_headers()

    resp_body = f'Response after {delay} seconds'
    request_handler.wfile.write(resp_body.encode('utf-8'))
