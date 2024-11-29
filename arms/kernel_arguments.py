# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
class LinuxKernelArguments:

    def __init__(self, *arguments: tuple[str, str]):
        self._arguments = list(arguments)

    def as_line(self) -> str:
        result = []
        for argument, value in self._arguments:
            if value:
                result.append(f'{argument}={value}')
            else:
                result.append(argument)
        return ' '.join(result)

    def with_arguments(self, *arguments: tuple[str, str]) -> 'LinuxKernelArguments':
        return self.__class__(*self._arguments, *arguments)

    def __repr__(self):
        arguments_line = self.as_line()
        return f'<{self.__class__.__name__}: [{arguments_line}]>'
