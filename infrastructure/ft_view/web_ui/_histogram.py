# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import math
import statistics
from collections import Counter
from typing import Sequence


class Histogram:
    """Simple histogram from 0 to limit with outliers to the right.

    >>> h = Histogram(10, 30, [
    ...     ('green', 11), ('green', 12), ('green', 18),
    ...     ('green', 22), ('green', 27), ('gray', 27), ('red', 28),
    ...     ('green', 33),
    ... ])
    >>> h.histogram
    [<Bin empty>, <Bin 3green>, <Bin 2green 1gray 1red>, <Bin 1green>]
    """

    def __init__(self, granularity, upper_limit, tagged_values):
        self.upper_limit = upper_limit
        axis = Axis(granularity, upper_limit)
        self.histogram = [Bin() for _ in range(axis.bin_count())]
        self.percentiles = Percentiles()
        self.height = 1
        total_bin = Bin()  # For common tag order through entire histogram
        for tag, value in tagged_values:
            current_bin = self.histogram[axis.bin_index(value)]
            current_bin.add(tag)
            self.height = max(self.height, current_bin.total_height())
            self.percentiles.add(tag, value)
            total_bin.add(tag)
        self.tags = total_bin.tags()


class Bin:

    def __init__(self):
        self._counters = Counter()

    def __repr__(self):
        if self._counters:
            text = ' '.join(f'{n}{tag}' for tag, n in self._counters.items())
        else:
            text = 'empty'
        return f"<Bin {text}>"

    def add(self, tag):
        self._counters[tag] += 1

    def tags(self):
        return [tag for tag, n in self._counters.most_common()]

    def total_height(self):
        return self._counters.total()

    def height(self, tag: str):
        return self._counters[tag]


class Axis:

    def __init__(self, granularity, upper_limit):
        self._range = range(0, upper_limit, granularity)

    def bin_count(self):
        return len(self._range) + 1  # Plus outliers

    def bin_index(self, x):
        if x < 0:
            raise ValueError("Must be greater than 0")
        elif x < self._range.stop:
            return int(x // self._range.step)
        else:
            return -1  # Outlier


class Percentiles:
    """Calculate percentiles.

    >>> p = Percentiles()
    >>> assert p.percentiles('foo', [50, 75, 100]) == {}
    >>> p.add('foo', 1)
    >>> p.add('foo', 4)
    >>> p.add('foo', 6)
    >>> p.add('foo', 10)
    >>> r = p.percentiles('foo', [50, 75, 100])
    >>> assert 4 <= r[50] <= 6
    >>> assert 6 <= r[75] <= 10
    >>> assert 9.99 < r[100] < 10.01
    """

    def __init__(self):
        self._values = {}

    def add(self, tag: str, value: float):
        if tag not in self._values:
            self._values[tag] = []
        self._values[tag].append(value)

    def percentiles(self, tag: str, stops: Sequence[float]):
        t = math.gcd(*stops)
        n = 100 // t
        values = self._values.get(tag, [])
        if len(values) < 2:
            return {}
        borders = statistics.quantiles(values, n=n) + [max(values)]
        return {p: borders[int(p // t) - 1] for p in stops}
