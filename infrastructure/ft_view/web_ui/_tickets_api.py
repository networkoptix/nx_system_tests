# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json

from flask import Blueprint
from flask import current_app
from flask import request

from infrastructure.ft_view import _db
from infrastructure.ft_view.web_ui._urls import _redirect_back

tickets_blueprint = Blueprint(
    'tickets',
    __name__,
    )


@tickets_blueprint.route('/tickets/link', methods=['POST'])
def _link():
    params = request.form
    current_app.logger.info("Link ticket: %s", params['ticket'])
    _db.write(
        'UPDATE run '
        'SET run_ticket = %(ticket)s '
        'WHERE run_json @> %(args)s '
        ';', {
            'args': json.dumps(request.args),
            'ticket': params['ticket'],
            })
    return _redirect_back()


@tickets_blueprint.route('/tickets/unlink', methods=['POST'])
def _unlink():
    _db.write(
        'UPDATE run '
        'SET run_ticket = NULL '
        'WHERE run_json @> %(args)s '
        ';', {
            'args': json.dumps(request.args),
            })
    return _redirect_back()
