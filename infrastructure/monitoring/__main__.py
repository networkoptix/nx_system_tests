# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from http.server import HTTPServer

from infrastructure._logging import init_logging
from infrastructure._uri import get_process_uri
from infrastructure.monitoring._app import make_app

if __name__ == '__main__':
    init_logging(get_process_uri())
    app = make_app()
    server = HTTPServer(('0.0.0.0', 8050), app)
    server.serve_forever()
