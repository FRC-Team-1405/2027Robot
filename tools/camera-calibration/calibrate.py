#!/usr/bin/env python3
"""
Camera Mount Calibration Tool entry point.
Run:  streamlit run calibrate.py
"""
from camera_calibration.app import _running_under_streamlit, _streamlit_app

if _running_under_streamlit():
    _streamlit_app()
elif __name__ == '__main__':
    print('Run with:  streamlit run calibrate.py')
