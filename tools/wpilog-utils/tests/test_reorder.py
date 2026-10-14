"""reorder.py: an out-of-order log (plain WPILib DataLogManager's NT mirroring) back in time order,
nothing lost -- checked by verify_reorder and by reading both files back."""
import struct

import pytest

import wpilog_builder as wb
from wpilog_utils.decode import parse_wpilog_bytes
from wpilog_utils.index import build_index
from wpilog_utils.reorder import REORDER_ENTRY, order_report, reorder_log, verify_reorder


def set_metadata(entry_id: int, ts_us: int, meta: str) -> bytes:
    m = meta.encode()
    return wb.record(0, ts_us, b'\x02' + struct.pack('<I', entry_id) + struct.pack('<I', len(m)) + m)


def late_log() -> bytes:
    """Main-loop entry 1 every 20 ms; entry 2 (mirrored telemetry) written 5 ms late, after entry 1's newer record."""
    raw = wb.header('') + wb.start(1, '/Loop', 'double', '') + wb.start(2, 'NT:/DriveState/Pose', 'double', '')
    raw += wb.start(3, 'NT:/Unused', 'double', '', ts_us=500)                       # declared, never written
    raw += set_metadata(2, 900, '{"late":true}')                                     # before entry 2's first record
    for i in range(10):
        t = 1_000 + 20_000 * i
        raw += wb.record(1, t, wb.double(i))
        if i:
            raw += wb.record(2, t - 5_000, wb.double(100 + i))                       # 5 ms behind entry 1's record
    raw += wb.finish(2, 150_000)                                                     # before entry 2's last record
    raw += wb.record(1, 400_000, wb.double(99))
    return raw


def test_report_counts_late_records():
    rep = order_report(late_log())
    assert rep.n_records == 20 and rep.n_late == 9 and rep.max_late_us == 5_000 and rep.n_backwards == 0
    assert rep.lateness == {'< 20 ms': 9}
    assert [e.name for e in rep.entries] == ['NT:/DriveState/Pose']


def test_reordered_copy_is_in_order_and_complete():
    raw = late_log()
    out, st = reorder_log(raw, 'FRC_x.wpilog')
    assert verify_reorder(out, raw).ok
    assert st.n_moved == 9 and st.control_folded == 1
    ix = build_index(out)
    assert ix.time_ordered and ix.n_late_records == 0
    assert order_report(out).ordered
    before, after = parse_wpilog_bytes(raw), parse_wpilog_bytes(out)
    for name in before:                                    # every signal identical, sample for sample
        assert after[name] == before[name]
    assert REORDER_ENTRY.lstrip('/') in after
    names = {e.name: e for e in ix.entries.values()}
    assert 'NT:/Unused' in names and names['NT:/DriveState/Pose'].metadata == '{"late":true}'


def test_the_checker_notices_a_lost_record():
    raw = late_log()
    out, _ = reorder_log(raw)
    lost = out[:-len(wb.record(1, 400_000, wb.double(99)))]
    assert not verify_reorder(lost, raw).ok


def test_index_counts_late_records():
    ix = build_index(late_log())
    assert not ix.time_ordered and ix.n_late_records == 9 and ix.max_late_us == 5_000


def test_parser_stats_count_late_records():
    stats = {}
    parse_wpilog_bytes(late_log(), stats)
    assert stats['n_late'] == 9 and stats['max_late_s'] == pytest.approx(0.005)


def test_reused_entry_ids_are_refused():
    raw = wb.header('') + wb.start(1, '/a', 'double', '') + wb.record(1, 10, wb.double(1)) + wb.finish(1, 20)
    raw += wb.start(1, '/b', 'double', '', ts_us=30) + wb.record(1, 40, wb.double(2))
    with pytest.raises(ValueError, match='started twice'):
        reorder_log(raw)
