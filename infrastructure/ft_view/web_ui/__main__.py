# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from infrastructure.ft_view.web_ui.app import app

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=5002,
        debug=False,
        threaded=False,
        )
