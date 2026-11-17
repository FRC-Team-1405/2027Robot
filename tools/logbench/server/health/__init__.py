"""Health Check: a configuration-driven set of "is this thing OK?" checks over any signal source.

The same checks run against a live robot (NetworkTables) in the pits and against a finished
.wpilog afterwards. A check is a few lines of TOML (see health_checks.toml); adding a new metric
means adding a block there, with no code change. See config.py for the vocabulary, engine.py for
how a check is evaluated, and docs/health-check.md.
"""
