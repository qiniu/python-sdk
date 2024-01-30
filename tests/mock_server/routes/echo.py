import http
import logging
from urllib.parse import parse_qs


def handle_echo(method, parsed_uri, request_handler):
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
    echo_status = parse_qs(parsed_uri.query).get('status')
    if not echo_status:
        echo_status = http.HTTPStatus.BAD_REQUEST
        logging.error('No echo status specified')
        echo_body = f'param status is required'
    else:
        echo_status = int(echo_status[0])
        echo_body = f'Response echo status is {echo_status}'

    request_handler.send_response(echo_status)
    request_handler.send_header('Content-Type', 'text/plain')
    request_handler.send_header('X-Reqid', 'mocked-req-id')
    request_handler.end_headers()

    request_handler.wfile.write(echo_body.encode('utf-8'))
