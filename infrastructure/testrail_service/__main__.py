# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from http.server import HTTPServer

from infrastructure.testrail_service._app import make_app

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    app = make_app()
    server = HTTPServer(('0.0.0.0', 8090), app)
    server.serve_forever()
