"""Re-pick a log's Pi sessions once the log itself is on disk and its true clock can be read.

The Fetch Bundle page suggests sessions from file names alone (pairing.suggest_pairings). After the
download the log says exactly which boot it is (log_clock.py), so the bundle job swaps the guess for
an exact selection: every session of that boot whose frames overlap the log's own time range, however
many short pieces the recorder split the match into. The user's hand-picked sessions are never
touched (`manual`).
"""
import dataclasses
import datetime as dt
import pathlib
from typing import List, Optional

import log_clock
import pairing


@dataclasses.dataclass
class Refined:
    sessions: List[dict]          # [{camera, name, pi}]
    method: str                   # 'epoch' | 'requested'
    note: str
    clock: Optional[log_clock.LogClock] = None


def _key(s) -> tuple:
    return (s['pi'], s['camera'], s['name'])


def refine(local_log: pathlib.Path, requested: List[dict], pi_raw: List[dict]) -> Refined:
    """requested/pi_raw are dicts as main.py holds them ({camera, name, pi, ...}). Falls back to
    `requested` unchanged, with a note saying why, whenever the epoch cannot be used."""
    clock = log_clock.read_file(local_log)
    if clock.epoch is None:
        return Refined(requested, 'requested',
                       'this log does not record its wall clock (robot code before WallClockEpoch); '
                       'sessions were picked from the file name', clock)
    rio = pairing.RioLogInfo(name=local_log.name, wall_clock=None, duration_sec=clock.duration_sec,
                             epoch=clock.epoch, boot_id=clock.boot_id, t_range=clock.t_range)
    infos = [pairing.PiSessionInfo(camera=s['camera'], name=s['name'], wall_clock=s.get('wall_clock'),
                                   pi=s.get('pi', ''), epoch=s.get('epoch'),
                                   t_first=s.get('t_first'), t_last=s.get('t_last'))
             for s in pi_raw]
    chosen = pairing.select_for_log(rio, infos)
    if chosen is None:
        return Refined(requested, 'requested',
                       'no Pi session shares this log\'s boot clock (epoch %s); kept the file-name pick'
                       % clock.epoch.isoformat(timespec='seconds'), clock)
    refined = [{'camera': s.camera, 'name': s.name, 'pi': s.pi} for s in chosen.pi_sessions]
    # Requested sessions that carry no clock to compare (older recorder, unreadable manifest) stay.
    clockless = {_key(s) for s in pi_raw if s.get('epoch') is None}
    listed = {_key(s) for s in pi_raw}
    seen = {_key(s) for s in refined}
    keep = [s for s in requested if _key(s) not in seen and (_key(s) in clockless or _key(s) not in listed)]
    refined.extend(keep)
    old = {_key(s) for s in requested}
    new = {_key(s) for s in refined}
    note = ('picked %d session(s) by boot clock: %d added, %d dropped from the file-name suggestion'
            % (len(refined), len(new - old), len(old - new)))
    return Refined(refined, 'epoch', note, clock)
