(function () {
  'use strict';
  var state = {};
  var root = document.getElementById('stage');
  var mctx = document.createElement('canvas').getContext('2d');
  var esc = window.ACTemplate.esc;
  var M = window.ACMotion;
  var FONT = "'PingFang SC', 'Noto Sans SC', 'Helvetica Neue', Impact, sans-serif";

  var intro = { y: -40, scale: 1.35, opacity: 0, barW: 0 };
  var tl = M.createTimeline()
    .fromTo(intro, { y: -36, scale: 1.28, opacity: 0 }, { y: 0, scale: 1.0, opacity: 1 }, 0.05, 0.34, 'back.out')
    .fromTo(intro, { barW: 0 }, { barW: 1 }, 0.16, 0.38, 'expo.out');

  function measureW(text, sz, wt) {
    mctx.font = (wt || 800) + ' ' + sz + 'px ' + FONT;
    return Math.max(1, mctx.measureText(text).width);
  }

  window.setData = function (fill) { state = fill || {}; };

  window.renderFrame = M.bindTimeline(tl, function (t) {
    var lang = state.audience_language || 'zh';
    var accent = M.getVar(state, 'accent_color', '#FFE548');
    var scaleKey = M.getVar(state, 'font_scale', 'M');
    var fScale = ({ S: 0.86, M: 1.0, L: 1.15 })[String(scaleKey).toUpperCase()] || 1.0;

    var parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">'];
    parts.push(M.renderVignette(0.62));

    var topText = (state.kicker || (state.title_lines && state.title_lines[0]) || '').trim();
    if (topText && intro.opacity > 0.02) {
      var badge = topText.slice(0, 20).toUpperCase();
      var bw = Math.min(820, Math.round(measureW(badge, 32, 900) + 64));
      var wipeW = Math.round(bw * intro.barW);
      parts.push('<g transform="translate(540,' + (176 + intro.y).toFixed(1) + ') scale(' + intro.scale.toFixed(3) + ')" opacity="' + intro.opacity.toFixed(3) + '">');
      parts.push('<rect x="' + (-bw / 2).toFixed(1) + '" y="-30" width="' + wipeW + '" height="60" rx="14" fill="' + accent + '"/>');
      parts.push('<text x="0" y="11" text-anchor="middle" font-family="' + FONT + '" font-size="32" font-weight="900" letter-spacing="1.5" fill="#111216">' + esc(badge) + '</text>');
      parts.push('</g>');
    }

    var moment = window.ACTemplate.momentAt(state, t);
    var chunks = M.chunkCaption(moment, lang, 4);
    var digest = 'SLAM_IDLE_' + Math.round(intro.barW * 20);
    if (chunks.length) {
      var mStart = (moment.t0 != null ? moment.t0 : moment.start) || 0;
      var mEnd = (moment.t1 != null ? moment.t1 : moment.end) || (mStart + 2.0);
      var age = Math.max(0, t - mStart);
      var prog = M.clamp01(age / Math.max(0.2, mEnd - mStart));
      var activeIdx = M.staggerIndex(chunks.length, prog);
      var sep = lang === 'en' ? ' ' : '';
      var full = chunks.join(sep);
      var fz = Math.round((full.length > 18 ? 48 : 58) * fScale);
      var slam = M.kineticSlam(age, 0.22);
      var totalW = 0;
      for (var i = 0; i < chunks.length; i++) {
        totalW += measureW(chunks[i], fz, 900) + (i > 0 ? (sep ? measureW(sep, fz, 900) : 10) : 0);
      }
      var xCur = Math.max(60, (1080 - totalW) / 2);
      parts.push('<g transform="translate(540,1455) scale(' + slam.scale.toFixed(3) + ') translate(-540,-1455)" opacity="' + slam.opacity.toFixed(3) + '">');
      for (var j = 0; j < chunks.length; j++) {
        var tok = chunks[j];
        var tw = measureW(tok, fz, 900);
        var isAct = j === activeIdx;
        if (isAct) {
          parts.push('<rect x="' + (xCur - 8).toFixed(1) + '" y="' + (1455 - fz + 2).toFixed(1) + '" width="' + (tw + 16).toFixed(1) + '" height="' + (fz + 18).toFixed(1) + '" rx="12" fill="' + accent + '"/>');
          parts.push('<text x="' + xCur.toFixed(1) + '" y="1463" font-family="' + FONT + '" font-size="' + fz + '" font-weight="900" fill="#111216">' + esc(tok) + '</text>');
        } else {
          parts.push('<text x="' + xCur.toFixed(1) + '" y="1463" font-family="' + FONT + '" font-size="' + fz + '" font-weight="900" fill="#FFFFFF" stroke="#0B0C10" stroke-width="11" paint-order="stroke" stroke-linejoin="round">' + esc(tok) + '</text>');
        }
        xCur += tw + (sep ? measureW(sep, fz, 900) : 10);
      }
      parts.push('</g>');
      digest = 'SLAM_' + full + '_' + activeIdx + '_' + accent + '_' + scaleKey;
    }

    parts.push('</svg>');
    root.innerHTML = parts.join('');
    return digest;
  });

  window.occupiedRects = function () { return [{ slot: 'caption', x: 60, y: 1380, w: 960, h: 140 }]; };
})();
