/* Highlight Note (Ali Abdaal productivity sticker style) — 1080x1920 @ 30fps, deterministic, zero external URLs. */
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

  function measureW(text, sz) {
    mctx.font = '800 ' + sz + 'px "PingFang SC", "Noto Sans CJK SC", "Helvetica Neue", sans-serif';
    return Math.max(1, mctx.measureText(text).width);
  }

  function isEnglish(s) {
    return /^[\x20-\x7e\u2014\u2018\u2019\u201c\u201d\u2026]+$/.test(String(s || '').trim());
  }

  function wrapTokens(tokens, sz, maxW, padX, gapX) {
    var lines = [];
    var cur = [];
    var curW = 0;
    for (var i = 0; i < tokens.length; i++) {
      var tw = measureW(tokens[i].text, sz) + padX * 2;
      if (cur.length && curW + gapX + tw > maxW) {
        lines.push({ items: cur, width: curW });
        cur = [{ text: tokens[i].text, active: tokens[i].active, w: tw }];
        curW = tw;
      } else {
        cur.push({ text: tokens[i].text, active: tokens[i].active, w: tw });
        curW = cur.length === 1 ? tw : (curW + gapX + tw);
      }
    }
    if (cur.length) lines.push({ items: cur, width: curW });
    return lines.slice(0, 3);
  }

  window.setData = function (fill) {
    state = fill || {};
  };

  window.renderFrame = function (tSeconds) {
    var t = Number(tSeconds) || 0;
    var titleText = (state.title_lines || []).join(' ').trim();
    var kicker = String(state.kicker || '').trim();
    var lang = state.audience_language || 'en';
    var moment = window.ACTemplate ? window.ACTemplate.momentAt(state, t) : null;

    var svg = '<defs>'
      + '<linearGradient id="topV" x2="0" y2="1"><stop offset="0%" stop-color="#0B0C10" stop-opacity="0.58"/><stop offset="100%" stop-color="#0B0C10" stop-opacity="0"/></linearGradient>'
      + '<linearGradient id="botV" x2="0" y2="1"><stop offset="0%" stop-color="#0B0C10" stop-opacity="0"/><stop offset="100%" stop-color="#0B0C10" stop-opacity="0.72"/></linearGradient>'
      + '<filter id="cardSh" x="-10%" y="-10%" width="120%" height="130%"><feDropShadow dx="0" dy="6" stdDeviation="6" flood-color="#000000" flood-opacity="0.34"/></filter>'
      + '</defs>';

    svg += '<rect x="0" y="0" width="1080" height="360" fill="url(#topV)"/>';
    svg += '<rect x="0" y="1140" width="1080" height="780" fill="url(#botV)"/>';

    // Yellow highlighter tape headline (stays crisp at top safe zone)
    var headerDigest = '';
    if (titleText) {
      var hSize = 48;
      var hText = isEnglish(titleText) ? titleText.toLowerCase() : titleText;
      var hw = measureW(hText, hSize);
      if (hw > 760) {
        hSize = Math.max(30, Math.floor((hSize * 760) / hw));
        hw = measureW(hText, hSize);
      }
      var boxW = Math.min(860, Math.round(hw + 58));
      var boxH = Math.round(hSize * 1.65);
      var bx = Math.round(540 - boxW / 2);
      var by = 188;
      svg += '<g transform="rotate(-1.4 540 ' + (by + boxH / 2) + ')" filter="url(#cardSh)">'
        + '<rect x="' + bx + '" y="' + by + '" width="' + boxW + '" height="' + boxH + '" rx="10" fill="#FFE852"/>'
        + '<text x="540" y="' + (by + Math.round(boxH / 2 + hSize * 0.34)) + '" text-anchor="middle" font-size="' + hSize + '" font-weight="800" fill="#141418" letter-spacing="0.5">' + esc(hText) + '</text>'
        + '</g>';
      if (kicker) {
        svg += '<text x="540" y="' + (by - 18) + '" text-anchor="middle" font-size="24" font-weight="700" fill="#FFFDF5" opacity="0.88" letter-spacing="2">' + esc(kicker.toUpperCase()) + '</text>';
      }
      headerDigest = hText + '|' + kicker;
    }

    // White sticker block kinetic captions in lower-third safe zone
    var capDigest = '';
    if (moment && moment.zh && moment.zh.length) {
      var parts = [];
      for (var i = 0; i < moment.zh.length; i++) {
        if (moment.zh[i] && moment.zh[i].s) parts.push(moment.zh[i].s);
      }
      var raw = parts.join(lang === 'en' ? ' ' : '').trim();
      if (raw) {
        var useEn = lang === 'en' || isEnglish(raw);
        var mStart = Number(moment.start || 0);
        var mEnd = Number(moment.end || (mStart + 1.5));
        var frac = Math.max(0, Math.min(0.999, (t - mStart) / Math.max(0.08, mEnd - mStart)));
        var tokens = [];
        if (useEn) {
          var words = raw.split(/\s+/).filter(Boolean);
          var actIdx = Math.floor(frac * words.length);
          for (var w = 0; w < words.length; w++) {
            tokens.push({ text: words[w], active: w === actIdx });
          }
          capDigest = raw + '@' + actIdx;
        } else {
          // Split Chinese sentence into 2-4 char sticker chunks for crisp kinetic highlight
          var chunks = [];
          var clean = raw.replace(/\s+/g, '');
          var step = clean.length <= 8 ? 2 : 3;
          for (var c = 0; c < clean.length; c += step) chunks.push(clean.slice(c, c + step));
          var actZh = Math.floor(frac * chunks.length);
          for (var k = 0; k < chunks.length; k++) {
            tokens.push({ text: chunks[k], active: k === actZh });
          }
          capDigest = clean + '@' + actZh;
        }

        var sz = useEn ? 50 : 48;
        var padX = 18;
        var gapX = 10;
        var lines = wrapTokens(tokens, sz, 880, padX, gapX);
        var lineH = Math.round(sz * 1.52);
        var gapY = 12;
        var totalH = lines.length * lineH + (lines.length - 1) * gapY;
        var startY = Math.round(1380 - totalH / 2);

        var capSvg = '<g filter="url(#cardSh)">';
        for (var li = 0; li < lines.length; li++) {
          var row = lines[li];
          var rx = Math.round(540 - row.width / 2);
          var ry = startY + li * (lineH + gapY);
          for (var ti = 0; ti < row.items.length; ti++) {
            var it = row.items[ti];
            var bg = it.active ? '#FFE852' : '#FFFFFF';
            capSvg += '<rect x="' + rx + '" y="' + ry + '" width="' + Math.round(it.w) + '" height="' + lineH + '" rx="12" fill="' + bg + '"/>';
            capSvg += '<text x="' + Math.round(rx + it.w / 2) + '" y="' + (ry + Math.round(lineH / 2 + sz * 0.34)) + '" text-anchor="middle" font-size="' + sz + '" font-weight="800" fill="#141418">' + esc(it.text) + '</text>';
            rx += Math.round(it.w) + gapX;
          }
        }
        capSvg += '</g>';
        svg += capSvg;
      }
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return headerDigest + '||' + capDigest;
  };

  window.occupiedRects = function () {
    return [
      { slot: 'hook', x: 110, y: 170, w: 860, h: 110 },
      { slot: 'caption', x: 100, y: 1240, w: 880, h: 280 },
    ];
  };
})();
