# Vision Comparison Summary

## Log A — akit_26-06-20_13-33-46_baseline.wpilog
- Window: 22.9s – 39.9s (17.0s of 57.1s total)
- Format: new, Cameras: Left, Right

## Log B — akit_26-06-20_15-20-19_decimateBack.wpilog
- Window: 36.8s – 52.7s (15.9s of 191.6s total)
- Format: new, Cameras: Left, Right

## Summary

| Metric | Left A | Left B | Δ Left | Right A | Right B | Δ Right |
|---|---|---|---|---|---|---|
| Acceptance rate (%) | 98.22 | 98.29 | +0.07 | 99.03 | 99.47 | +0.44 |
| FPS mean | 77.92 | 64.83 | -13.09 | 61.91 | 60.6 | -1.31 |
| FPS min | 57.22 | 57.07 | -0.15 | 54.53 | 50.73 | -3.8 |
| Connection uptime (%) | 0 | 0 | +0 | 0 | 0 | +0 |
| Mean result latency (ms) | 26.7 | 24.7 | -2 | 25.2 | 25.9 | +0.7 |
| Rejected velocity (%) | 18.41 | 26.03 | +7.62 | 17.73 | 18.89 | +1.16 |
| Rejected boundary (%) | 0 | 0 | +0 | 0 | 0 | +0 |
| Rejected ambiguity (%) | 0 | 0 | +0 | 0 | 0 | +0 |
| Stationary quality (%) | 100 | 100 | +0 | 99.61 | 99.05 | -0.56 |

## Acceptance

| Metric | Left A | Left B | Δ Left | Right A | Right B | Δ Right |
|---|---|---|---|---|---|---|
| Total accepted poses | 1211 | 978 | -233 | 1022 | 932 | -90 |
| Total raw results | 1233 | 995 | -238 | 1032 | 937 | -95 |
| Accepted poses per second (avg) | 71.381 | 61.599 | -9.782 | 60.241 | 58.702 | -1.539 |

## Health

| Metric | Left A | Left B | Δ Left | Right A | Right B | Δ Right |
|---|---|---|---|---|---|---|
| Latency sample count | 1230 | 992 | -238 | 1027 | 935 | -92 |
| Pose stddev X, 100-sample window (mm) mean | 168.45 | 221.546 | +53.096 | 213.338 | 238.348 | +25.01 |
| Pose stddev X, 100-sample window (mm) min | 1.124 | 0.8 | -0.324 | 0.693 | 0.609 | -0.084 |
| Pose stddev X, 100-sample window (mm) max | 637.677 | 623.736 | -13.941 | 653.002 | 640.089 | -12.913 |
| Pose stddev Y, 100-sample window (mm) mean | 184.366 | 226.242 | +41.876 | 227.24 | 246.432 | +19.192 |
| Pose stddev Y, 100-sample window (mm) min | 1.634 | 1.051 | -0.583 | 0.771 | 0.482 | -0.289 |
| Pose stddev Y, 100-sample window (mm) max | 640.367 | 612.534 | -27.833 | 668.994 | 659.735 | -9.259 |
| Pose stddev theta, 100-sample window (deg) mean | 8.4593 | 10.9207 | +2.4614 | 10.8669 | 11.7756 | +0.9087 |
| Pose stddev theta, 100-sample window (deg) min | 0.0471 | 0.0366 | -0.0105 | 0.0296 | 0.0233 | -0.0063 |
| Pose stddev theta, 100-sample window (deg) max | 18.5948 | 22.9346 | +4.3398 | 22.8247 | 23.6257 | +0.801 |
| Pose stddev X, 1s window (mm) mean | 112.528 | 132.5 | +19.972 | 119.685 | 134.359 | +14.674 |
| Pose stddev X, 1s window (mm) min | 0.942 | 0.836 | -0.106 | 0.687 | 0.563 | -0.124 |
| Pose stddev X, 1s window (mm) max | 553.405 | 532.876 | -20.529 | 493.669 | 509.114 | +15.445 |
| Pose stddev Y, 1s window (mm) mean | 123.708 | 136.091 | +12.383 | 140.281 | 147.993 | +7.712 |
| Pose stddev Y, 1s window (mm) min | 1.459 | 0.955 | -0.504 | 0.724 | 0.494 | -0.23 |
| Pose stddev Y, 1s window (mm) max | 514.214 | 462.239 | -51.975 | 457.476 | 456.205 | -1.271 |
| Pose stddev theta, 1s window (deg) mean | 6.0554 | 6.7039 | +0.6485 | 5.9883 | 6.5805 | +0.5922 |
| Pose stddev theta, 1s window (deg) min | 0.0409 | 0.0379 | -0.003 | 0.0279 | 0.0215 | -0.0064 |
| Pose stddev theta, 1s window (deg) max | 16.3141 | 16.9373 | +0.6232 | 16.1611 | 16.8623 | +0.7012 |

## Motion

| Metric | Left A | Left B | Δ Left | Right A | Right B | Δ Right |
|---|---|---|---|---|---|---|
| Stationary acceptance rate (%) | 100 | 100 | +0 | 99.61 | 99.05 | -0.56 |
| Stationary sample count | 257 | 222 | -35 | 259 | 211 | -48 |
| Slow translate acceptance rate (%) | 97.06 | 97.88 | +0.82 | 98.87 | 99.31 | +0.44 |
| Slow translate sample count | 384 | 448 | +64 | 381 | 408 | +27 |
| Rotating acceptance rate (%) | 0 | 100 | +100 | 0 | 100 | +100 |
| Rotating sample count | 0 | 3 | +3 | 0 | 3 | +3 |
| Full speed acceptance rate (%) | 0 | 0 | +0 | 0 | 0 | +0 |
| Full speed sample count | 0 | 0 | +0 | 0 | 0 | +0 |

## Geometry

| Metric | Left A | Left B | Δ Left | Right A | Right B | Δ Right |
|---|---|---|---|---|---|---|
| Distance (m) mean | 1.13 | 1.156 | +0.026 | 1.108 | 1.134 | +0.026 |
| Distance (m) min | 0.883 | 0.847 | -0.036 | 0.946 | 0.905 | -0.041 |
| Distance (m) max | 1.776 | 1.836 | +0.06 | 1.636 | 1.682 | +0.046 |
| Tag area (sum) mean | 4.03 | 3.592 | -0.438 | 3.576 | 3.322 | -0.254 |
| Tag area (sum) min | 0.596 | 0.508 | -0.088 | 0.493 | 0.421 | -0.072 |
| Tag area (sum) max | 6.992 | 7.613 | +0.621 | 5.142 | 5.596 | +0.454 |
| Z height (m) mean | -0.037 | -0.029 | +0.008 | -0.043 | -0.04 | +0.003 |
| Z height (m) min | -0.152 | -0.143 | +0.009 | -0.146 | -0.097 | +0.049 |
| Z height (m) max | 0.03 | 0.028 | -0.002 | 0.031 | 0.029 | -0.002 |
| Ambiguity (single-tag) mean | 0.011 | 0.01 | -0.001 | 0.004 | 0.005 | +0.001 |
| Ambiguity (single-tag) min | 0 | 0 | +0 | 0 | 0.001 | +0.001 |
| Ambiguity (single-tag) max | 0.037 | 0.026 | -0.011 | 0.022 | 0.145 | +0.123 |
| Multi-tag count | 741 | 446 | -295 | 552 | 422 | -130 |
| Single-tag count | 189 | 259 | +70 | 246 | 266 | +20 |
| Multi-tag rate (%) | 79.68 | 63.26 | -16.42 | 69.17 | 61.34 | -7.83 |

## Field

| Metric | Left A | Left B | Δ Left | Right A | Right B | Δ Right |
|---|---|---|---|---|---|---|
| Unique tags seen | 8 | 8 | +0 | 8 | 8 | +0 |
| Total tag detections | 1618 | 1092 | -526 | 1266 | 1034 | -232 |
| Rejected boundary poses (count) | 0 | 0 | +0 | 0 | 0 | +0 |
| Rejected velocity poses (count) | 27 | 19 | -8 | 11 | 8 | -3 |
| Rejected ambiguity poses (count) | 0 | 0 | +0 | 0 | 0 | +0 |
