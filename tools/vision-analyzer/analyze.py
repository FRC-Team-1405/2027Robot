#!/usr/bin/env python3
"""
Vision Log Analyzer entry point.
Run:  streamlit run analyze.py
      python analyze.py --probe path/to/log.wpilog
"""
from vision_analyzer.app import _running_under_streamlit, _streamlit_app
from vision_analyzer.cli import _cli_main

if _running_under_streamlit():
    _streamlit_app()
elif __name__ == '__main__':
    _cli_main()
