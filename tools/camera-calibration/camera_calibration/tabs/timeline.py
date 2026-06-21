"""Tab 2 — Timeline: velocity chart and stationary window preview."""
import streamlit as st

LABEL = '2 · Timeline'


def render(ctx: dict) -> None:
    signals = ctx.get('signals')
    start_t = ctx.get('start_t', 0.0)

    if signals is None:
        st.info('Load a `.wpilog` file in the sidebar to see the velocity timeline.')
        return

    import sys, pathlib
    _va = pathlib.Path(__file__).parents[3] / 'vision-analyzer'
    if str(_va) not in sys.path:
        sys.path.insert(0, str(_va))
    from vision_analyzer.metrics import find_drivetrain_speeds

    lin_key, ang_key = find_drivetrain_speeds(signals)
    if not lin_key and not ang_key:
        st.warning(
            'No drivetrain speed signals found in this log. '
            '(Expected one of: `Drivetrain/Speeds/vxMetersPerSecond`, '
            '`SwerveDrivetrain/ChassisSpeeds/vx`, etc.)'
        )
        st.markdown('**Available signals containing "speed":**')
        speed_keys = [k for k in signals if 'speed' in k.lower()]
        st.code('\n'.join(speed_keys[:30]) if speed_keys else '(none)')
        return

    import plotly.graph_objects as go

    lin_sig = signals[lin_key] if lin_key else []
    ang_sig = signals[ang_key] if ang_key else []

    lin_ts = [t - start_t for t, _ in lin_sig]
    lin_vs = [abs(float(v)) for _, v in lin_sig]
    ang_ts = [t - start_t for t, _ in ang_sig]
    ang_vs = [abs(float(v)) for _, v in ang_sig]

    fig = go.Figure()

    if lin_ts:
        fig.add_trace(go.Scatter(
            x=lin_ts, y=lin_vs,
            name='Linear speed (m/s)',
            line=dict(color='#4FC3F7', width=1.5),
        ))
    if ang_ts:
        fig.add_trace(go.Scatter(
            x=ang_ts, y=ang_vs,
            name='Angular speed (rad/s)',
            line=dict(color='#AED581', width=1.5),
            yaxis='y2',
        ))

    # Stationary threshold lines
    fig.add_hline(y=0.06, line_dash='dot', line_color='rgba(255,100,100,0.5)',
                  annotation_text='lin thresh', annotation_position='right',
                  row=None, col=None)

    fig.update_layout(
        template='plotly_dark',
        height=320,
        yaxis=dict(title='Linear speed (m/s)', range=[0, max(lin_vs + [1.0])]),
        yaxis2=dict(title='Angular speed (rad/s)', overlaying='y', side='right',
                    range=[0, max(ang_vs + [1.0])]),
        xaxis=dict(title='Time (s from log start)'),
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
        margin=dict(l=50, r=60, t=30, b=40),
        plot_bgcolor='#111827',
        paper_bgcolor='#111827',
    )

    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # Show auto-detected windows as a compact info block
    windows = ctx.get('_detected_windows', [])
    if windows:
        st.markdown(f'**Auto-detected stationary windows:** {len(windows)} found '
                    f'(≥2 s, linear < 0.06 m/s, angular < 0.06 rad/s)')
        rows = [f'W{i+1}: {w[0]-start_t:.1f} s – {w[1]-start_t:.1f} s  '
                f'({w[1]-w[0]:.1f} s)'
                for i, w in enumerate(windows)]
        st.code('\n'.join(rows))
    else:
        st.info(
            'No stationary windows detected yet. '
            'Go to **3 · Session** to run detection and assign poses.'
        )
