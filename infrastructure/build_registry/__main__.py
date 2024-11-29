# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from http.server import HTTPServer
from pathlib import Path

from infrastructure._logging import init_logging
from infrastructure._uri import get_process_uri
from infrastructure.build_registry._app import make_app
from infrastructure.build_registry.builds_database import SqliteLastUsageDatabase

if __name__ == '__main__':
    init_logging(get_process_uri())
    db_path = Path(__file__).parent / 'builds.db'
    app = make_app(SqliteLastUsageDatabase(db_path))
    server = HTTPServer(('0.0.0.0', 9090), app)
    server.request_queue_size = 128
    server.serve_forever()
