# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import date
from datetime import timedelta
from typing import Optional

from flask import g

from infrastructure.ft_view._enrichment import period_keys


class DateFilter:

    def __init__(self, date_param: Optional[str]):
        self._today = g.today
        if date_param is None:
            self._focus_day = self._today
        else:
            self._focus_day = date.fromisoformat(date_param)

    def today(self) -> date:
        return self._today

    def focus_day(self) -> date:
        return self._focus_day

    def previous_day(self) -> date:
        return self._focus_day + timedelta(days=-1)

    def next_day(self) -> date:
        return self._focus_day + timedelta(days=1)

    def current_period(self) -> str:
        return min(period_keys(self._today))
