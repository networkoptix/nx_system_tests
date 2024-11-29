# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import unittest
from pathlib import Path
from uuid import UUID

from mediaserver_api.analytics import AnalyticsEngineCollection
from mediaserver_api.analytics import AnalyticsEngineNotFound


class TestAnalyticsEngine(unittest.TestCase):

    def test_empty_collection(self):
        collection = AnalyticsEngineCollection(raw=[])
        with self.assertRaises(AnalyticsEngineNotFound):
            collection.get_by_exact_name('ANY NAME')
        with self.assertRaises(AnalyticsEngineNotFound):
            collection.get_stub('ANY NAME')
        self.assertEqual(len(collection.list_engines()), 0)

    def test_non_empty_collection_for_regular_plugin(self):
        collection = AnalyticsEngineCollection(_read_json('raw_engines_stub_with_colon.json'))
        engine = collection.get_by_exact_name('Uniview')
        self.assertEqual(engine.id(), UUID('1c6e620d-5f16-f2a7-8baa-3d9f2e7d9085'))
        self.assertEqual(engine.name(), 'Uniview')

    def test_non_empty_collection_for_stub_with_colon(self):
        collection = AnalyticsEngineCollection(_read_json('raw_engines_stub_with_colon.json'))
        engine = collection.get_stub('Best Shots')
        self.assertEqual(engine.id(), UUID('5d5dc4ea-f9a4-1e6d-6598-a50dd1ee7a0e'))
        self.assertEqual(engine.name(), 'Stub: Best Shots')

    def test_non_empty_collection_for_stub_with_comma(self):
        collection = AnalyticsEngineCollection(_read_json('raw_engines_stub_with_comma.json'))
        engine = collection.get_stub('Object Streamer')
        self.assertEqual(engine.id(), UUID('570687b4-4876-5841-bfbe-1d24a9914ffa'))
        self.assertEqual(engine.name(), 'Stub, Object Streamer')

    def test_non_empty_collection_for_unknown_plugin(self):
        collection = AnalyticsEngineCollection(_read_json('raw_engines_stub_with_comma.json'))
        with self.assertRaises(AnalyticsEngineNotFound):
            collection.get_by_exact_name('UNKNOWN NAME')
        with self.assertRaises(AnalyticsEngineNotFound):
            collection.get_stub('UNKNOWN NAME')

    def test_all_engines_found(self):
        raw_engines = _read_json('raw_engines_stub_with_comma.json')
        collection = AnalyticsEngineCollection(raw_engines)
        self.assertEqual(len(collection.list_engines()), len(raw_engines))

    def test_stub_name_variants(self):
        collection_1 = AnalyticsEngineCollection(_read_json('raw_engines_stub_with_colon.json'))
        engine_1 = collection_1.get_stub('Best Shots', 'Best Shots and Titles')
        self.assertEqual(engine_1.id(), UUID('5d5dc4ea-f9a4-1e6d-6598-a50dd1ee7a0e'))
        self.assertEqual(engine_1.name(), 'Stub: Best Shots')
        collection_2 = AnalyticsEngineCollection(_read_json('raw_engines_stub_with_comma.json'))
        engine_2 = collection_2.get_stub('Best Shots', 'Best Shots and Titles')
        self.assertEqual(engine_2.id(), UUID('5d5dc4ea-f9a4-1e6d-6598-a50dd1ee7a0e'))
        self.assertEqual(engine_2.name(), 'Stub, Best Shots and Titles')


def _read_json(file_name: str):
    path = Path(__file__).parent / file_name
    return json.loads(path.read_text())
