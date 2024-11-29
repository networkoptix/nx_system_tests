# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from mediaserver_api.analytics import BoundingBox
from tests.analytics.helpers.track import Track
from tests.analytics.helpers.trajectory import Speed

tracks = [
    Track(
        start_frame_number=0,
        end_frame_number=20,
        type_id='_service_start',
        attributes={},
        speed=Speed(0, 0),
        init_bounding_box=BoundingBox(0, 0, 0, 0),
        ),
    Track(
        start_frame_number=221,
        end_frame_number=280,
        type_id='nx.base.Car',
        attributes={
            'Color': 'White',
            'Brand': 'Toyota',
            'Number': '1',
            },
        speed=Speed(0, 0.04),
        init_bounding_box=BoundingBox(0, 0, 0.2, 0.2),
        ),
    Track(
        start_frame_number=250,
        end_frame_number=310,
        type_id='nx.base.Person',
        attributes={
            'Race': 'Caucasian',
            'Height cm': '170',
            'Number': '2',
            },
        speed=Speed(0.03, 0),
        init_bounding_box=BoundingBox(0, 0.8, 0.2, 1),
        ),
    Track(
        start_frame_number=280,
        end_frame_number=340,
        type_id='nx.base.Car',
        attributes={
            'Color': 'White',
            'Brand': 'Toyota',
            'Number': '3',
            },
        speed=Speed(0, -0.04),
        init_bounding_box=BoundingBox(0.8, 0.8, 1, 1),
        ),
    Track(
        start_frame_number=310,
        end_frame_number=370,
        type_id='nx.base.Person',
        attributes={
            'Race': 'Caucasian',
            'Height cm': '170',
            'Number': '4',
            },
        speed=Speed(-0.03, 0),
        init_bounding_box=BoundingBox(0.8, 0, 1, 0.2),
        ),
    Track(
        start_frame_number=340,
        end_frame_number=400,
        type_id='nx.base.Car',
        attributes={
            'Color': 'White',
            'Brand': 'Toyota',
            'Number': '5',
            },
        speed=Speed(0.03, 0.03),
        init_bounding_box=BoundingBox(0.2, 0.2, 0.4, 0.4),
        ),
    Track(
        start_frame_number=370,
        end_frame_number=430,
        type_id='nx.base.Person',
        attributes={
            'Race': 'Caucasian',
            'Height cm': '170',
            'Number': '6',
            },
        speed=Speed(0.03, -0.03),
        init_bounding_box=BoundingBox(0.2, 0.6, 0.4, 0.8),
        ),
    Track(
        start_frame_number=400,
        end_frame_number=460,
        type_id='nx.base.Person',
        attributes={
            'Race': 'Caucasian',
            'Height cm': '170',
            'Number': '7',
            },
        speed=Speed(0, 0.03),
        init_bounding_box=BoundingBox(0.2, 0, 0.4, 0.2),
        ),
    Track(
        start_frame_number=430,
        end_frame_number=490,
        type_id='nx.base.Car',
        attributes={
            'Color': 'White',
            'Brand': 'Toyota',
            'Number': '8',
            },
        speed=Speed(0, -0.04),
        init_bounding_box=BoundingBox(0.4, 0.8, 0.6, 1),
        ),
    Track(
        start_frame_number=460,
        end_frame_number=520,
        type_id='nx.base.Person',
        attributes={
            'Race': 'Caucasian',
            'Height cm': '170',
            'Number': '9',
            },
        speed=Speed(0.05, 0),
        init_bounding_box=BoundingBox(0.6, 0.2, 0.8, 0.4),
        ),
    Track(
        start_frame_number=490,
        end_frame_number=550,
        type_id='nx.base.Car',
        attributes={
            'Color': 'White',
            'Brand': 'Toyota',
            'Number': '10',
            },
        speed=Speed(-0.05, 0),
        init_bounding_box=BoundingBox(0.6, 0.4, 0.8, 0.6),
        ),
    Track(
        start_frame_number=580,
        end_frame_number=600,
        type_id='_service_finish',
        attributes={},
        speed=Speed(0, 0),
        init_bounding_box=BoundingBox(0, 0, 0, 0),
        ),
    ]
