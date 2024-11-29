# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
class Version(tuple):  # `tuple` gives `__hash__` and comparisons but requires `__new__`.

    def __new__(cls, version_str):
        return super(Version, cls).__new__(cls, list(map(int, version_str.split('.', 3))))

    def __init__(self, version_str):
        super(Version, self).__init__()
        self.major, self.minor, self.fix, self.build = self
        self.as_str = version_str
        self.short = self.major, self.minor

    def __repr__(self):
        return 'Version({!r})'.format(self.as_str)

    def __str__(self):
        return self.as_str
