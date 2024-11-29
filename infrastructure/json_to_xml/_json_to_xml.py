# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from io import StringIO
from typing import Any
from xml.sax.saxutils import XMLGenerator


def json_to_xml(data):
    if not isinstance(data, (list, dict)):
        raise ValueError(f'Data must be list or dict, got {type(data)}')
    buffer = StringIO()
    _to_xml('root', data, XMLGenerator(buffer))
    return buffer.getvalue()


def _to_xml(name: str, data: Any, xml_generator: XMLGenerator):
    xml_generator.startElement(name, {})
    if isinstance(data, dict):
        for key, value in data.items():
            _to_xml(key, value, xml_generator)
    elif isinstance(data, list):
        for item in data:
            _to_xml('item', item, xml_generator)
    elif isinstance(data, (str, float)):
        xml_generator.characters(str(data))
    elif isinstance(data, int) and not isinstance(data, bool):
        xml_generator.characters(str(data))
    else:
        raise RuntimeError(f"Cannot convert {data!r} (type {type(data)})")
    xml_generator.endElement(name)
