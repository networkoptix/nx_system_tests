# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import importlib
import json
from pathlib import Path

from tests.analytics.helpers.track import Track


def make_object_stream_from_tracks(*tracks: Track):
    result = []
    for idx, track in enumerate(tracks, start=1):
        for frame_attributes in track.frame_attributes:
            result.append({
                'frameNumber': frame_attributes.frame_number,
                'typeId': track.type_id,
                'trackId': f'$${idx}',
                'attributes': track.attributes,
                'boundingBox': frame_attributes.bounding_box.as_bounding_box_dict(),
                })
    return result


def load_tracks_from_file(tracks_file: Path):
    spec = importlib.util.spec_from_file_location(tracks_file.stem, str(tracks_file))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.tracks


def dump_object_stream_to_file(output_file: Path, object_stream):
    to_save = json.dumps(
        object_stream,
        indent=4,
        )
    output_file.write_text(to_save)
