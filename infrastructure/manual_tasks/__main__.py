# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from http.server import HTTPServer

from infrastructure.manual_tasks._app import make_app

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    app = make_app()
    server = HTTPServer(('0.0.0.0', 9080), app)
    server.serve_forever()
