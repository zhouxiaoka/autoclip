/* Clean White Pill (Ali Abdaal minimal white-pill caption style) — 1080x1920 @ 30fps. */
(function () {
  'use strict';

  var state = {};
  var root = document.getElementById('stage');
  var mctx = document.createElement('canvas').getContext('2d');

  function esc(v) {
    return String(v || '').replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[c];
    });
  }

  function measureW(text, sz, weight) {
    mctx.font = (weight || 700) + ' ' + sz + 'px "Inter", "PingFang SC", "Noto Sans CJK SC", "Helvetica Neue", sans-serif';
    return Math.max(1, mctx.measureText(text).width);
  }

  window.setData = function (fill) {
    state = fill || {};
  };

  window.renderFrame = function (tSeconds) {
    var t = Number(tSeconds) || 0;
    var titleText = (state.title_lines || []).join(' ').trim();
    var lang = state.audience_language || 'en';
    var moment = window.ACTemplate ? window.ACTemplate.momentAt(state, t) : null;

    var svg = '<defs>'
      + '<filter id="pillSh" x="-15%" y="-20%" width="130%" height="150%"><feDropShadow dx="0" dy="6" stdDeviation="8" flood-color="#000000" flood-opacity="0.28"/></filter>'
      + '</defs>';

    // Subtle auto-dismissing top title pill (0..2.6s only, zero clutter afterwards)
    var hookAlpha = t < 2.2 ? 1 : (t < 2.7 ? Math.max(0, 1 - (t - 2.2) / 0.5) : 0);
    var hookStep = hookAlpha > 0 ? hookAlpha.toFixed(2) : '0';
    var headDigest = '';
    if (hookAlpha > 0.01 && titleText) {
      var hsz = 34;
      var hw = measureW(titleText, hsz, 700);
      if (hw > 760) {
        hsz = Math.max(24, Math.floor((hsz * 760) / hw));
        hw = measureW(titleText, hsz, 700);
      }
      var pw = Math.min(840, Math.round(hw + 52));
      var ph = Math.round(hsz * 1.85);
      var px = Math.round(540 - pw / 2);
      var py = 176;
      svg += '<g opacity="' + hookStep + '" filter="url(#pillSh)">'
        + '<rect x="' + px + '" y="' + py + '" width="' + pw + '" height="' + ph + '" rx="' + Math.round(ph / 2) + '" fill="#141418" fill-opacity="0.78"/>'
        + '<text x="540" y="' + (py + Math.round(ph / 2 + hsz * 0.34)) + '" text-anchor="middle" font-size="' + hsz + '" font-weight="700" fill="#FFFFFF">' + esc(titleText) + '</text>'
        + '</g>';
      headDigest = titleText + '@' + hookStep;
    }

    // Minimal crisp white pill caption in lower-third safe zone (never covers face/hands)
    var capDigest = '';
    if (moment && moment.zh && moment.zh.length) {
      var parts = [];
      for (var i = 0; i < moment.zh.length; i++) {
        if (moment.zh[i] && moment.zh[i].s) parts.push(moment.zh[i].s);
      }
      var raw = parts.join(lang === 'en' ? ' ' : '').trim();
      if (raw) {
        var csz = 42;
        var cw = measureW(raw, csz, 700);
        if (cw > 820) {
          csz = Math.max(28, Math.floor((csz * 820) / cw));
          cw = measureW(raw, csz, 700);
        }
        var boxW = Math.min(900, Math.round(cw + 48));
        var boxH = Math.round(csz * 1.72);
        var bx = Math.round(540 - boxW / 2);
        var by = 1420;
        svg += '<g filter="url(#pillSh)">'
          + '<rect x="' + bx + '" y="' + by + '" width="' + boxW + '" height="' + boxH + '" rx="14" fill="#FFFFFF" fill-opacity="0.96"/>'
          + '<text x="540" y="' + (by + Math.round(boxH / 2 + csz * 0.34)) + '" text-anchor="middle" font-size="' + csz + '" font-weight="700" fill="#141418">' + esc(raw) + '</text>'
          + '</g>';
        capDigest = raw;
      }
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return headDigest + '||' + capDigest;
  };

  window.occupiedRects = function () {
    return [
      { slot: 'caption', x: 90, y: 1400, w: 900, h: 90 },
    ];
  };
})();
