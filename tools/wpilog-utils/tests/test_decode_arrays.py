"""Array payload decoding, string[] in particular (dropped as "unrecognized" until 11-07)."""
import struct

import wpilog_builder as wb
from wpilog_utils.decode import decode_payload, parse_wpilog_bytes


def string_array(items):
    out = struct.pack('<I', len(items))
    for s in items:
        b = s.encode('utf-8')
        out += struct.pack('<I', len(b)) + b
    return out


def test_string_array_round_trip():
    names = ['VisionRunner - /1119', 'Thread-20/1120', '', 'naïve']
    assert decode_payload(string_array(names), 'string[]') == names


def test_empty_string_array():
    assert decode_payload(string_array([]), 'string[]') == []
    assert decode_payload(b'', 'string[]') == []


def test_truncated_string_array_is_dropped_not_misread():
    good = string_array(['abc', 'defgh'])
    assert decode_payload(good[:-2], 'string[]') is None
    assert decode_payload(struct.pack('<I', 3), 'string[]') is None


def test_string_array_survives_parse_wpilog_next_to_its_numbers():
    b = wb.LogBuilder()
    names = b.entry('/RealOutputs/OrangePi/LeftPi/PvTopThreads', 'string[]')
    pcts = b.entry('/RealOutputs/OrangePi/LeftPi/PvTopThreadPct', 'double[]')
    b.data(names, 1_000_000, string_array(['VisionRunner - /1119', 'Thread-20/1120']))
    b.data(pcts, 1_000_000, struct.pack('<2d', 64.0, 10.0))
    sig = parse_wpilog_bytes(b.build())
    assert sig['RealOutputs/OrangePi/LeftPi/PvTopThreads'] == [(1.0, ['VisionRunner - /1119', 'Thread-20/1120'])]
    assert sig['RealOutputs/OrangePi/LeftPi/PvTopThreadPct'] == [(1.0, [64.0, 10.0])]
