"""Prepare a portable post-match archive, keeping the fetched source unchanged."""
import dataclasses
import json
import logging
import pathlib
import zipfile

import battery
import battery_export
from core.log import Log
from wpilog_utils.decode import parse_wpilog_bytes
from wpilog_utils.index import build_index
from wpilog_utils.reorder import reorder_log, verify_reorder
from wpilog_utils.trim import (MATCH_CONTEXT_ENTRIES, MATCH_CONTEXT_PREFIXES, TrimPlan,
                               mode_segments, resolve_plan, trim_log)
from wpilog_utils.verify import verify_trim


log = logging.getLogger(__name__)


def trimmed_name(source_name: str) -> str:
    return pathlib.Path(source_name).stem + '.trimmed.wpilog'


def report_name(source_name: str) -> str:
    return pathlib.Path(source_name).stem + '.trim.json'


def battery_report_names(source_name: str) -> tuple[str, str]:
    stem = pathlib.Path(source_name).stem
    return stem + '.battery.html', stem + '.battery.json'


def prepare(source: pathlib.Path, sessions: list[pathlib.Path], output: pathlib.Path,
            phase=lambda text: None, cancelled=lambda: False, include_battery=False) -> dict:
    """Write a ZIP and, when processing succeeds, a verified trimmed copy.

    sessions is the explicit fetched selection, so old local sessions cannot sneak
    into a later download. All flat session files (including recorder.log) are kept.
    Processing failures keep the original downloadable with a warning/report, never
    an unverified derived log. Filesystem errors and cancellation still fail the job.
    """
    def check():
        if cancelled():
            raise RuntimeError('cancelled by user')

    check()
    output.mkdir(parents=True, exist_ok=True)
    phase('Trimming enabled periods')
    original = source.read_bytes()
    raw = original
    warnings = []
    stats = None
    reordered = False
    trim_error = None
    try:
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
    except (ValueError, OverflowError) as exc:
        # Fetches are valuable even when the log cannot be safely processed.
        # Never publish an unverified derived log or discard the original.
        log.warning('Could not trim %s; archiving original and recordings: %s', source.name, exc)
        trim_error = str(exc)
        trimmed = None
        stats = None
        warnings.append(f'Trimming failed: {exc}. ZIP contains the unchanged original log and recordings; no trimmed copy was created.')
    check()
    copy = output / trimmed_name(source.name) if trimmed is not None else None
    if copy is not None:
        copy.write_bytes(trimmed)
    report = {
        'source': source.name, 'trimmed': copy.name if copy else None, 'timestamps': 'preserved',
        'trim_status': 'failed' if trim_error else ('trimmed' if stats else 'full-original'),
        'trim_error': trim_error,
        'modes': ['auto', 'teleop', 'test'], 'padding_seconds': 2,
        'reordered_working_copy': reordered, 'warnings': warnings,
        'source_bytes': len(original), 'trimmed_bytes': len(trimmed) if trimmed is not None else None,
        'stats': dataclasses.asdict(stats) if stats else None,
    }
    report_file = output / report_name(source.name)
    battery_files = []
    if include_battery and trim_error:
        warnings.append('Battery analysis was skipped because log processing failed; the full original is included for diagnosis.')
    if include_battery and not trim_error:
        check()
        phase('Analyzing battery on full original log')
        # Use the exact source snapshot, never the trimmed/reordered working copy.
        analysis = battery.analyze(Log(path=source, signals=parse_wpilog_bytes(original)))
        exported = battery_export.export_json(analysis)
        exported['analysis_scope'] = 'full-original-log'
        html_name, json_name = battery_report_names(source.name)
        html_file, json_file = output / html_name, output / json_name
        html_file.write_text(battery_export.render_html(analysis), encoding='utf-8')
        json_file.write_text(battery_export.dumps(exported), encoding='utf-8')
        battery_files = [html_file, json_file]
        check()
    report_file.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    phase('Creating downloadable ZIP')
    archive = output / (source.stem + '-bundle.zip')
    partial = archive.with_suffix('.zip.part')
    try:
        with zipfile.ZipFile(partial, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Archive the exact input used by the trim, even if another fetch of
            # the same RIO filename updates the local source during processing.
            zf.writestr(source.name, original)
            for file in ([copy] if copy else []) + [report_file, *battery_files]:
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
    result = {'archive': archive.name, 'warnings': warnings,
              'battery_reports': [file.name for file in battery_files]}
    if copy is not None:
        result['trimmed_log'] = copy.name
    return result
