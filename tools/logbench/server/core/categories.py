"""The three kinds of question a vision metric can answer, and the one place that says so.

A metric belongs to exactly one category, decided by whether a low reading tells you *what to
fix* (docs/adr/0001, D1) -- two metrics with different remedies are different categories:

  availability  Does usable data arrive when it should?        -> connection, mount/FOV, exposure, USB
  quality       When a tag is seen, how good is the solution?  -> calibration, focus, threshold, decimate
  context       What conditions was this measured under?       -> nothing; it explains the other two

Context is never scored: it describes the run (how fast the robot moved, how close the tags
were), not the camera, so folding it into a score turns "we drove a different route" into "the
camera got better". `SCORED` is the structural guard -- tests/test_categories.py fails if any
composite in a scored category (or overall) depends, directly or transitively, on a context metric.

'overall' and 'legacy' are not question categories, they only place composites: 'overall' is the
optional availability x quality product; 'legacy' is composites/scores that predate this split and
mix categories (kept so existing scripts keep working, and labelled so nobody mistakes them for it).
"""
from dataclasses import dataclass
from typing import Dict, List, Tuple

AVAILABILITY = 'availability'
QUALITY = 'quality'
CONTEXT = 'context'
OVERALL = 'overall'
LEGACY = 'legacy'

# Categories whose members are allowed to feed a score.
SCORED = (AVAILABILITY, QUALITY)


@dataclass(frozen=True)
class Category:
    id: str
    label: str
    question: str
    low_means: str
    scored: bool


CATEGORIES: Tuple[Category, ...] = (
    Category(AVAILABILITY, 'Availability', 'Does usable data arrive when it should?',
             'Look at the connection, camera mount and field of view, exposure or lighting, '
             'USB or network.', True),
    Category(QUALITY, 'Quality', 'When a tag is seen, how good is the solution?',
             'Look at calibration, focus, the tag detection threshold, decimate.', True),
    Category(CONTEXT, 'Context', 'What conditions was this measured under?',
             'Nothing is wrong with the camera. This explains why the other numbers moved '
             '(different route, speed or range). Never scored.', False),
)

LEGACY_LABEL = 'Legacy composites'
OVERALL_LABEL = 'Overall'

BY_ID: Dict[str, Category] = {c.id: c for c in CATEGORIES}
ALL_IDS: List[str] = [AVAILABILITY, QUALITY, CONTEXT, OVERALL, LEGACY]


def describe() -> List[dict]:
    """JSON-ready listing for the API and the export."""
    return [
        {'id': c.id, 'label': c.label, 'question': c.question, 'low_means': c.low_means,
         'scored': c.scored}
        for c in CATEGORIES
    ]
