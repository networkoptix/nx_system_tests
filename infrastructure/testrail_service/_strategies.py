# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from abc import ABCMeta
from abc import abstractmethod
from typing import Collection
from typing import List
from typing import NamedTuple
from typing import Sequence


def get_strategy_registry():
    return _StrategyRegistry(strategy_apply_order=[
        _ConfigToTag("Ubuntu 16.04", 'ubuntu16'),
        _ConfigToTag("Ubuntu 18.04", 'ubuntu18'),
        _ConfigToTag("Ubuntu 20.04", 'ubuntu20'),
        _ConfigToTag("Windows Server 2019", 'win2019'),
        _ConfigToTag("Windows Server 2022", 'win2022'),
        _ConfigToTag("Jetson TX2", 'jetson_tx2'),
        _ConfigToTag("Raspberry Pi 3", 'rpi3'),
        _ConfigToTag("Raspberry Pi 4", 'rpi4'),
        _ConfigToAnyTag("Windows", [
            'win10',
            'win11',
            'win2019',
            'win2022',
            ]),
        _ConfigToAnyTag("Linux", [
            'ubuntu16',
            'ubuntu18',
            'ubuntu20',
            'ubuntu22',
            ]),
        _ConfigToAnyTag("macOS", [
            'macos',
            ]),
        _ConfigToAnyTag("ARM", [
            'rpi3',
            'rpi4',
            'jetson_tx2',
            ]),
        _SkipConfig("Cloud test"),
        _SkipConfig("Any OS"),  # Sometimes we don't have knowledge about stage machines layout
        ])


class _StrategyResult(NamedTuple):
    matched: bool
    tags: Collection[str] = []


class _MatchStrategy(metaclass=ABCMeta):

    @abstractmethod
    def match(self, tags: List[str]) -> '_StrategyResult':
        pass

    @abstractmethod
    def is_suitable(self, config: str) -> bool:
        pass


class _BaseStrategy(_MatchStrategy, metaclass=ABCMeta):

    def __init__(self, testrail_config: str):
        self._config = testrail_config

    def is_suitable(self, config: str) -> bool:
        return config.startswith(self._config)


class _ConfigToTag(_BaseStrategy):

    def __init__(self, testrail_config: str, ft_tag: str):
        super().__init__(testrail_config)
        self._ft_tag = ft_tag

    def match(self, job_tags: Collection[str]) -> _StrategyResult:
        if self._ft_tag in job_tags:
            return _StrategyResult(
                matched=True,
                tags=[self._ft_tag],
                )
        else:
            return _StrategyResult(matched=False, tags=[self._ft_tag])


class _ConfigToAnyTag(_BaseStrategy):

    def __init__(self, testrail_config: str, possible_ft_tags: Collection[str]):
        super().__init__(testrail_config)
        self._possible_ft_tags = possible_ft_tags

    def match(self, job_tags: Collection[str]):
        for possible_tag in self._possible_ft_tags:
            if possible_tag in job_tags:
                return _StrategyResult(
                    matched=True,
                    tags=[possible_tag],
                    )
        return _StrategyResult(
            matched=False,
            tags=self._possible_ft_tags,
            )


class _SkipConfig(_BaseStrategy):

    def match(self, job_tags: List[str]):
        return _StrategyResult(True)


class _UnknownConfig(_MatchStrategy):

    def __init__(self, testrail_config: str):
        self._config = testrail_config

    def match(self, job_tags: List[str]):
        return _StrategyResult(False)

    def is_suitable(self, config: str) -> bool:
        return True


class _StrategyRegistry:

    def __init__(self, *, strategy_apply_order: Sequence[_MatchStrategy]):
        self._strategies = strategy_apply_order

    def _find_strategy_by_config(self, testrail_config: str) -> _MatchStrategy:
        for strategy in self._strategies:
            if strategy.is_suitable(testrail_config):
                return strategy
        return _UnknownConfig(testrail_config)

    def match_configs_and_tags(self, configs: Sequence[str], job_tags: Collection[str]) -> bool:
        job_tags = [*job_tags]
        results = []
        for config in configs:
            strategy = self._find_strategy_by_config(config)
            strategy_result = strategy.match(job_tags)
            results.append(strategy_result)
            if strategy_result.matched:
                for matched_tag in strategy_result.tags:
                    job_tags.remove(matched_tag)
        return all(result.matched for result in results)
