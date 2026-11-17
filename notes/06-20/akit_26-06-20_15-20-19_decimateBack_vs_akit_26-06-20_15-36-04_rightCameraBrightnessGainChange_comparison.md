# Vision Comparison Summary

## Log A — akit_26-06-20_15-20-19_decimateBack.wpilog
- Window: 36.8s – 52.7s (15.9s of 191.6s total)
- Format: new, Cameras: Left, Right

## Log B — akit_26-06-20_15-36-04_rightCameraBrightnessGainChange.wpilog
- Window: 23.5s – 40.6s (17.1s of 51.8s total)
- Format: new, Cameras: Left, Right

## Summary

| Metric | Left A | Left B | Δ Left | Right A | Right B | Δ Right |
|---|---|---|---|---|---|---|
| Acceptance rate (%) | 98.29 | 98.97 | +0.68 | 99.47 | 98.9 | -0.57 |
| FPS mean | 64.83 | 63.16 | -1.67 | 60.6 | 80.08 | +19.48 |
| FPS min | 57.07 | 54.79 | -2.28 | 50.73 | 64.71 | +13.98 |
| Connection uptime (%) | 0 | 0 | +0 | 0 | 0 | +0 |
| Mean result latency (ms) | 24.7 | 27.4 | +2.7 | 25.9 | 24.9 | -1 |
| Rejected velocity (%) | 26.03 | 12.89 | -13.14 | 18.89 | 16.22 | -2.67 |
| Rejected boundary (%) | 0 | 0 | +0 | 0 | 0 | +0 |
| Rejected ambiguity (%) | 0 | 0 | +0 | 0 | 0 | +0 |
| Stationary quality (%) | 100 | 99.67 | -0.33 | 99.05 | 99.43 | +0.38 |

## Acceptance

| Metric | Left A | Left B | Δ Left | Right A | Right B | Δ Right |
|---|---|---|---|---|---|---|
| Total accepted poses | 978 | 1052 | +74 | 932 | 1354 | +422 |
| Total raw results | 995 | 1063 | +68 | 937 | 1369 | +432 |
| Accepted poses per second (avg) | 61.599 | 61.604 | +0.005 | 58.702 | 79.288 | +20.586 |

## Health

| Metric | Left A | Left B | Δ Left | Right A | Right B | Δ Right |
|---|---|---|---|---|---|---|
| Latency sample count | 992 | 1062 | +70 | 935 | 1362 | +427 |
| Pose stddev X, 100-sample window (mm) mean | 221.546 | 210.934 | -10.612 | 238.348 | 173.507 | -64.841 |
| Pose stddev X, 100-sample window (mm) min | 0.8 | 1.076 | +0.276 | 0.609 | 0.926 | +0.317 |
| Pose stddev X, 100-sample window (mm) max | 623.736 | 642.334 | +18.598 | 640.089 | 598.67 | -41.419 |
| Pose stddev Y, 100-sample window (mm) mean | 226.242 | 206.32 | -19.922 | 246.432 | 172.213 | -74.219 |
| Pose stddev Y, 100-sample window (mm) min | 1.051 | 1.279 | +0.228 | 0.482 | 1.742 | +1.26 |
| Pose stddev Y, 100-sample window (mm) max | 612.534 | 641.634 | +29.1 | 659.735 | 570.715 | -89.02 |
| Pose stddev theta, 100-sample window (deg) mean | 10.9207 | 10.4567 | -0.464 | 11.7756 | 8.1989 | -3.5767 |
| Pose stddev theta, 100-sample window (deg) min | 0.0366 | 0.049 | +0.0124 | 0.0233 | 0.0371 | +0.0138 |
| Pose stddev theta, 100-sample window (deg) max | 22.9346 | 21.8618 | -1.0728 | 23.6257 | 19.41 | -4.2157 |
| Pose stddev X, 1s window (mm) mean | 132.5 | 126.826 | -5.674 | 134.359 | 132.932 | -1.427 |
| Pose stddev X, 1s window (mm) min | 0.836 | 0.856 | +0.02 | 0.563 | 0.886 | +0.323 |
| Pose stddev X, 1s window (mm) max | 532.876 | 556.055 | +23.179 | 509.114 | 482.426 | -26.688 |
| Pose stddev Y, 1s window (mm) mean | 136.091 | 128.693 | -7.398 | 147.993 | 136.608 | -11.385 |
| Pose stddev Y, 1s window (mm) min | 0.955 | 1.139 | +0.184 | 0.494 | 1.729 | +1.235 |
| Pose stddev Y, 1s window (mm) max | 462.239 | 452.967 | -9.272 | 456.205 | 456.18 | -0.025 |
| Pose stddev theta, 1s window (deg) mean | 6.7039 | 6.2135 | -0.4904 | 6.5805 | 6.1664 | -0.4141 |
| Pose stddev theta, 1s window (deg) min | 0.0379 | 0.0456 | +0.0077 | 0.0215 | 0.037 | +0.0155 |
| Pose stddev theta, 1s window (deg) max | 16.9373 | 15.7845 | -1.1528 | 16.8623 | 15.97 | -0.8923 |

## Motion

| Metric | Left A | Left B | Δ Left | Right A | Right B | Δ Right |
|---|---|---|---|---|---|---|
| Stationary acceptance rate (%) | 100 | 99.67 | -0.33 | 99.05 | 99.43 | +0.38 |
| Stationary sample count | 222 | 254 | +32 | 211 | 265 | +54 |
| Slow translate acceptance rate (%) | 97.88 | 98.6 | +0.72 | 99.31 | 98.81 | -0.5 |
| Slow translate sample count | 448 | 392 | -56 | 408 | 404 | -4 |
| Rotating acceptance rate (%) | 100 | 0 | -100 | 100 | 0 | -100 |
| Rotating sample count | 3 | 0 | -3 | 3 | 0 | -3 |
| Full speed acceptance rate (%) | 0 | 0 | +0 | 0 | 0 | +0 |
| Full speed sample count | 0 | 0 | +0 | 0 | 0 | +0 |

## Geometry

| Metric | Left A | Left B | Δ Left | Right A | Right B | Δ Right |
|---|---|---|---|---|---|---|
| Distance (m) mean | 1.156 | 1.104 | -0.052 | 1.134 | 1.098 | -0.036 |
| Distance (m) min | 0.847 | 0.817 | -0.03 | 0.905 | 0.933 | +0.028 |
| Distance (m) max | 1.836 | 1.838 | +0.002 | 1.682 | 1.685 | +0.003 |
| Tag area (sum) mean | 3.592 | 3.788 | +0.196 | 3.322 | 3.313 | -0.009 |
| Tag area (sum) min | 0.508 | 0.524 | +0.016 | 0.421 | 0.512 | +0.091 |
| Tag area (sum) max | 7.613 | 7.507 | -0.106 | 5.596 | 6.103 | +0.507 |
| Z height (m) mean | -0.029 | -0.023 | +0.006 | -0.04 | -0.034 | +0.006 |
| Z height (m) min | -0.143 | -0.137 | +0.006 | -0.097 | -0.13 | -0.033 |
| Z height (m) max | 0.028 | 0.029 | +0.001 | 0.029 | 0.044 | +0.015 |
| Ambiguity (single-tag) mean | 0.01 | 0.009 | -0.001 | 0.005 | 0.005 | +0 |
| Ambiguity (single-tag) min | 0 | 0.001 | +0.001 | 0.001 | 0 | -0.001 |
| Ambiguity (single-tag) max | 0.026 | 0.036 | +0.01 | 0.145 | 0.033 | -0.112 |
| Multi-tag count | 446 | 481 | +35 | 422 | 565 | +143 |
| Single-tag count | 259 | 303 | +44 | 266 | 547 | +281 |
| Multi-tag rate (%) | 63.26 | 61.35 | -1.91 | 61.34 | 50.81 | -10.53 |

## Field

| Metric | Left A | Left B | Δ Left | Right A | Right B | Δ Right |
|---|---|---|---|---|---|---|
| Unique tags seen | 8 | 8 | +0 | 8 | 8 | +0 |
| Total tag detections | 1092 | 1200 | +108 | 1034 | 1550 | +516 |
| Rejected boundary poses (count) | 0 | 0 | +0 | 0 | 0 | +0 |
| Rejected velocity poses (count) | 19 | 13 | -6 | 8 | 22 | +14 |
| Rejected ambiguity poses (count) | 0 | 0 | +0 | 0 | 0 | +0 |
