"""Prepare a portable post-match archive, keeping the fetched source unchanged."""
import dataclasses
import json
import pathlib
import zipfile

from wpilog_utils.index import build_index
from wpilog_utils.reorder import reorder_log, verify_reorder
from wpilog_utils.trim import (MATCH_CONTEXT_ENTRIES, MATCH_CONTEXT_PREFIXES, TrimPlan,
                               mode_segments, resolve_plan, trim_log)
from wpilog_utils.verify import verify_trim


def trimmed_name(source_name: str) -> str:
    return pathlib.Path(source_name).stem + '.trimmed.wpilog'


def report_name(source_name: str) -> str:
    return pathlib.Path(source_name).stem + '.trim.json'


def prepare(source: pathlib.Path, sessions: list[pathlib.Path], output: pathlib.Path,
            phase=lambda text: None, cancelled=lambda: False) -> dict:
    """Write a verified trimmed copy and ZIP on disk; never write to the source.

    sessions is the explicit fetched selection, so old local sessions cannot sneak
    into a later download. All flat session files (including recorder.log) are kept.
    """
    def check():
        if cancelled():
            raise RuntimeError('cancelled by user')

    check()
    output.mkdir(parents=True, exist_ok=True)
    phase('Trimming enabled periods')
    original = source.read_bytes()
    raw = original
    index = build_index(raw)
    reordered = not index.time_ordered
    if reordered:
        phase('Ordering a working copy for trimming')
        raw, _ = reorder_log(raw, source.name)
        if not verify_reorder(raw, original).ok:
            raise ValueError('Time-order verification failed; original log was preserved.')
        index = build_index(raw)
    check()
    segments = mode_segments(index, ['auto', 'teleop', 'test'],
                             pad_pre_ms=2000, pad_post_ms=2000)
    warnings = []
    stats = None
    if segments:
        phase('Trimming and verifying copy')
        plan = TrimPlan(segments, gap_policy='preserve', source_name=source.name,
                        keep_everywhere=MATCH_CONTEXT_ENTRIES,
                        keep_everywhere_prefixes=MATCH_CONTEXT_PREFIXES)
        resolved = resolve_plan(index, plan)
        trimmed, stats = trim_log(raw, index, plan, resolved)
        if not verify_trim(trimmed, raw, index, plan, resolved).ok:
            raise ValueError('Trim verification failed; original log was preserved.')
        warnings.extend(resolved.warnings)
    else:
        trimmed = original
        warnings.append('No enabled periods were found. The trimmed copy contains the full original log.')
    check()
    copy = output / trimmed_name(source.name)
    copy.write_bytes(trimmed)
    report = {
        'source': source.name, 'trimmed': copy.name, 'timestamps': 'preserved',
        'modes': ['auto', 'teleop', 'test'], 'padding_seconds': 2,
        'reordered_working_copy': reordered, 'warnings': warnings,
        'source_bytes': len(original), 'trimmed_bytes': len(trimmed),
        'stats': dataclasses.asdict(stats) if stats else None,
    }
    report_file = output / report_name(source.name)
    report_file.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    phase('Creating downloadable ZIP')
    archive = output / (source.stem + '-bundle.zip')
    partial = archive.with_suffix('.zip.part')
    try:
        with zipfile.ZipFile(partial, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Archive the exact input used by the trim, even if another fetch of
            # the same RIO filename updates the local source during processing.
            zf.writestr(source.name, original)
            for file in (copy, report_file):
                check()
                zf.write(file, file.name)
            for session in sessions:
                for file in sorted(session.iterdir()):
                    check()
                    if file.is_file():
                        zf.write(file, file.relative_to(source.parent).as_posix())
        check()
        partial.replace(archive)
    finally:
        partial.unlink(missing_ok=True)
    return {'archive': archive.name, 'trimmed_log': copy.name, 'warnings': warnings}
