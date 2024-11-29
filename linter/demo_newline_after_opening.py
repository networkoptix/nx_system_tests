# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
_x = 123
_empty = []
_non_empty = [123]
_multiline_empty = [
    ]
_multiline_non_empty = [
    123,
    ]
_multiline_non_empty_wrong = [123,
                              ]
_multiline_non_empty_commented = [  # Comment
    123,
    ]
_multiline_non_empty_wrong_commented = [123,  # Comment
                                        ]
_nested = [[]]
_nested_2 = [[],
             ]
_nested_2a = [[]
              ]
_nested_2b = [1, []
              ]
_nested_3 = [[
    ]]
_nested_4 = [1, 2, 3, [
    ]]
_nested_5 = [
    [123],
    ]
_nested_6 = [], [
    ]
_nested_7 = [[
    ], [
    ]]

_iptables_rules_1 = [
    'OUTPUT -j REJECT',
    ]
_iptables_rules_2 = ['OUTPUT -o lo -j ACCEPT',
                     ]
_iptables_rules_3 = [
    'OUTPUT -o lo -j ACCEPT',
    'OUTPUT -d 10.0.0.0/22 -j ACCEPT',  # Office network
    'OUTPUT -d 10.0.8.0/24 -j ACCEPT',  # ARM network
    'OUTPUT -j REJECT']

sdp_headers = (
        b'v=0\r\n'  # SDP version
        b'o=- %(session_id)d %(version)d IN IP4 0.0.0.0\r\n'  # Owner info
        b's=NX FT RTSP Session\r\n'  # Session name
        b't=0 0\r\n'  # Start/stop media ts (may be zero)
        b'm=video 0 RTP/AVP %(payload_type)d\r\n'
        b'a=rtpmap:%(rtpmap)s\r\n'
        % {
            b'session_id': 123456789,
            b'version': 123456789,
            b'payload_type': 26,
            b'rtpmap': b'26 JPEG/90000',
            })
