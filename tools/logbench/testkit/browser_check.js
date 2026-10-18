// Paste into the browser console on a LogBench page opened with ?debug=1 (the debug flag exposes
// window.__player = {clock, spec}). Reads what the camera-feed panel is actually showing and
// compares it with the playhead. Works on bundles from testkit/build_bundle.py, whose frames have
// the log time (ms) and the camera number drawn on them; on other footage it still reports the
// selected camera, the video URL and the video position.
//
//   await lbCheck.snapshot(345)              // seek to log time 345 s and describe the feed
//   await lbCheck.switchCamera('RightCam')   // pick a camera in the panel's dropdown (or summary row)
//   await lbCheck.run([320, 345, 380])       // every camera at each time: sync + which feed
//
// The headless browser pane has no requestAnimationFrame, so everything here advances the clock
// with clock.renderNow().
window.lbCheck = (() => {
  const FONT = {0:'111101101101111',1:'010110010010111',2:'111001111100111',3:'111001111001111',4:'101101111001001',
    5:'111100111001111',6:'111100111101111',7:'111001001001001',8:'111101111101111',9:'111101111001111'};
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const tick = async (ms) => { const { clock } = window.__player; clock.renderNow(); await sleep(ms); clock.renderNow(); };

  function digits(ctx, w, h, row0, n, col0 = 0) {
    const bw = w / 40, bh = h / 30;
    const dark = (c, r) => ctx.getImageData(Math.floor((c + 0.5) * bw), Math.floor((r + 0.5) * bh), 1, 1).data[0] < 128;
    let s = '';
    for (let k = 0; k < n; k++) {
      let best = '?', top = -1;
      for (const [d, pat] of Object.entries(FONT)) {
        let sc = 0;
        for (let i = 0; i < 15; i++) if (dark(col0 + 4 * k + (i % 3), row0 + Math.floor(i / 3)) === (pat[i] === '1')) sc++;
        if (sc > top) { top = sc; best = d; }
      }
      s += best;
    }
    return s;
  }

  const select = () => document.querySelector('.vision__camera-select');

  async function switchCamera(name) {
    const sel = select();
    if (sel) {
      const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;
      setter.call(sel, name);
      sel.dispatchEvent(new Event('change', { bubbles: true }));
    } else {
      const row = [...document.querySelectorAll('.vision__summary-row')].find((r) => r.textContent.startsWith(name));
      if (row) row.click();
    }
    await tick(600);
    await sleep(2200);
    await tick(300);
  }

  async function snapshot(abs) {
    const { clock, spec } = window.__player;
    clock.pause();
    clock.seek(abs - spec.t0);
    await tick(500);
    await sleep(2200);
    await tick(300);
    const video = document.querySelector('.vision__video');
    const out = {
      logTime: abs,
      camera: select() ? select().value : null,
      mode: document.querySelector('.vision__mode')?.textContent ?? null,
    };
    if (!video || video.hidden) {
      out.video = 'hidden';
      out.placeholder = document.querySelector('.vision__placeholder')?.textContent ?? null;
      return out;
    }
    out.video = video.currentSrc.split('/vision-video/')[1];
    out.videoTime = +video.currentTime.toFixed(2);
    const c = document.createElement('canvas');
    c.width = video.videoWidth; c.height = video.videoHeight;
    const ctx = c.getContext('2d');
    ctx.drawImage(video, 0, 0);
    const burned = Number(digits(ctx, c.width, c.height, 1, 10));
    out.burnedLogTime = burned / 1000;
    out.syncErrorSec = +(burned / 1000 - abs).toFixed(2);
    out.burnedCameraNumber = Number(digits(ctx, c.width, c.height, 24, 1));
    return out;
  }

  async function run(times) {
    const { spec } = window.__player;
    const cams = [...(select() ? [...select().options].map((o) => o.value) : [])];
    const rows = [];
    for (const cam of cams) {
      await switchCamera(cam);
      for (const t of times) rows.push({ ...(await snapshot(t)), wanted: cam });
    }
    console.table(rows);
    return { cameras: cams, status: spec.static.vision_status, rows };
  }

  return { snapshot, switchCamera, run };
})();
'wired: lbCheck.snapshot(t) / lbCheck.switchCamera(name) / lbCheck.run([t...])';
