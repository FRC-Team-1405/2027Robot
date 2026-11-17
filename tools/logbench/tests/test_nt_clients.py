import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))

import paths  # noqa: F401

import nt_clients

SPANS = [(0, 10, 'disabled'), (10, 30, 'auto'), (30, 40, 'disabled')]


def test_reconnects_fold_into_one_client_and_brief_ones_are_left_out():
    signals = {
        'Anchor': [(0.0, 0), (40.0, 0)],
        # Elastic reconnected mid-auto under a new id: together it was there the whole time
        'SystemStats/NTClients/Elastic@2/Connected': [(0.0, True), (20.0, False)],
        'SystemStats/NTClients/Elastic@5/Connected': [(20.0, True)],
        # LogBench joined for the last 5 s of the 20 s auto: under half, so not counted
        'SystemStats/NTClients/Logbench@6/Connected': [(25.0, True)],
        'SystemStats/NTClients/AdvantageScope@1/Connected': [(0.0, True)],
    }
    shares = nt_clients.connected_share(signals, [(10.0, 30.0)])
    assert shares['Elastic'] == 0.5 and shares['Logbench'] == 0.25 and shares['AdvantageScope'] == 1.0
    (row,) = nt_clients.for_log(signals, SPANS, 0.0)
    assert row['display'] == '2' and row['detail'] == 'AdvantageScope, Elastic'


def test_a_log_without_client_stats_adds_nothing():
    assert nt_clients.for_log({'Anchor': [(0.0, 0), (40.0, 0)]}, SPANS, 0.0) == []
