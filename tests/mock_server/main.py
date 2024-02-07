import argparse
import http.server
import http.client
import logging
import sys
from urllib.parse import urlparse

from routes import routes


class MockHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.handle_request('GET')

    def do_POST(self):
        self.handle_request('POST')

    def do_PUT(self):
        self.handle_request('PUT')

    def do_DELETE(self):
        self.handle_request('DELETE')

    def do_OPTIONS(self):
        self.handle_request('OPTIONS')

    def do_HEAD(self):
        self.handle_request('HEAD')

    def handle_request(self, method):
        parsed_uri = urlparse(self.path)
        handle = routes.get(parsed_uri.path)
        if callable(handle):
            try:
                handle(method=method, parsed_uri=parsed_uri, request_handler=self)
            except Exception:
                logging.exception('Exception while handling.')
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'404 Not Found')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--port',
        type=int,
        default=8000,
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        datefmt='%Y-%m-%d %H:%M:%S',
        format='[%(asctime)s %(levelname)s] %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    server_address = ('', args.port)
    httpd = http.server.HTTPServer(server_address, MockHandler)
    logging.info('Mock Server running on port {}...'.format(args.port))

    httpd.serve_forever()
