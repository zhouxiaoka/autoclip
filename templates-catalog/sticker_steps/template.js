(function () {
  'use strict';
  var state = {};
  var root = document.getElementById('stage');
  var mctx = document.createElement('canvas').getContext('2d');
  var SANS = "'ACSpace', Inter, Helvetica, sans-serif";
  var POSTER = "'ACAnton', Impact, sans-serif";
  var SERIF = "'ACInstrument', Georgia, serif";
  var SCRIPT = "'ACPinyon', 'ACInstrument', cursive";
  var HAND = "'ACCaveat', cursive";

  function esc(v) {
    return String(v || '').replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[c];
    });
  }
  function clamp01(x) { return x < 0 ? 0 : (x > 1 ? 1 : x); }
  function easeOutQuint(x) { var p = clamp01(x); return 1 - Math.pow(1 - p, 5); }
  function easeOutCubic(x) { var p = clamp01(x); return 1 - Math.pow(1 - p, 3); }
  function spring(age, dur) {
    var p = clamp01(age / (dur || 0.28));
    if (p >= 1) return 1;
    return 1 - Math.exp(-7.5 * p) * Math.cos(9.5 * p);
  }
  function measureW(text, sz, weight, family, italic) {
    mctx.font = (italic ? 'italic ' : '') + (weight || 700) + ' ' + sz + 'px ' + (family || SANS);
    return Math.max(1, mctx.measureText(text).width);
  }
  function cueText(moment, lang) {
    if (!moment || !moment.zh || !moment.zh.length) return '';
    var parts = [];
    for (var i = 0; i < moment.zh.length; i++) {
      if (moment.zh[i] && moment.zh[i].s) parts.push(moment.zh[i].s);
    }
    return parts.join(lang === 'en' ? ' ' : '').trim();
  }
  function pickFocalIndex(words) {
    var stops = { the:1, a:1, an:1, to:1, of:1, in:1, on:1, for:1, and:1, or:1, is:1, are:1, was:1, that:1, with:1, your:1, you:1, we:1, it:1, into:1, from:1, this:1, just:1 };
    for (var i = 0; i < words.length; i++) {
      if (/\d/.test(words[i])) return i;
    }
    var best = Math.max(0, words.length - 1), bestLen = -1;
    for (var j = 0; j < words.length; j++) {
      var clean = words[j].toLowerCase().replace(/[^a-z0-9]/g, '');
      if (clean.length > bestLen && !stops[clean]) {
        bestLen = clean.length;
        best = j;
      }
    }
    return best;
  }
  function wrapLines(text, maxW, sz, weight, family, maxLines) {
    var words = String(text || '').trim().split(/\s+/).filter(Boolean);
    if (!words.length) return [];
    var lines = [], cur = words[0];
    for (var i = 1; i < words.length; i++) {
      var cand = cur + ' ' + words[i];
      if (measureW(cand, sz, weight, family) <= maxW) {
        cur = cand;
      } else {
        lines.push(cur);
        cur = words[i];
        if (maxLines && lines.length >= maxLines - 1) {
          lines.push(words.slice(i).join(' '));
          return lines;
        }
      }
    }
    lines.push(cur);
    return lines;
  }
  function momentIndex(t) {
    var list = (window.ACTemplate && window.ACTemplate.moments) ? window.ACTemplate.moments(state) : ((state && state.moments) || []);
    var idx = 0;
    for (var i = 0; i < list.length; i++) {
      var a = list[i].t0 != null ? list[i].t0 : list[i].start;
      var b = list[i].t1 != null ? list[i].t1 : list[i].end;
      if (t >= a && t < b) idx = i;
    }
    return idx;
  }
  window.setData = function (fill) { state = fill || {}; };

  window.renderFrame = function (tSeconds) {
    var t = Number(tSeconds) || 0;
    var lang = state.audience_language || 'en';
    var moment = window.ACTemplate ? window.ACTemplate.momentAt(state, t) : null;
    var raw = cueText(moment, lang);
    var mIdx = momentIndex(t);

    // Derive 3 step pill labels from title_lines (e.g. "STUFF · FOLD · VACUUM") or defaults
    var rawSteps = ((state.title_lines || []).join(' ') || 'STEP 1 · STEP 2 · STEP 3').split(/[·|,\/]+/).map(function (s) { return s.trim().toUpperCase(); }).filter(Boolean);
    var steps = rawSteps.length >= 3 ? rawSteps.slice(0, 3) : ['STEP 01', 'STEP 02', 'STEP 03'];
    var activeStep = Math.min(2, mIdx);

    var svg = '<defs>'
      + '<filter id="sh" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="6" stdDeviation="10" flood-color="#000" flood-opacity="0.52"/></filter>'
      + '</defs>';

    // Top 3 step pills above head (y=210) — active step glows crimson red (#EF4444), exact #31 vibe!
    var pillXs = [230, 540, 850];
    for (var s = 0; s < 3; s++) {
      var lbl = steps[s];
      var isAct = (s === activeStep);
      var pw = Math.max(150, Math.min(250, Math.round(measureW(lbl, 30, 700, SANS) + 46)));
      var pFill = isAct ? '#EF4444' : '#18181B';
      var pOp = isAct ? '0.96' : '0.78';
      var pSc = isAct ? (0.94 + 0.06 * spring(Math.max(0, t - ((moment && (moment.t0 != null ? moment.t0 : moment.start)) || 0)), 0.22)) : 1.0;
      svg += '<g transform="translate(' + pillXs[s] + ',216) scale(' + pSc.toFixed(3) + ')" filter="url(#sh)">'
        + '<rect x="' + (-pw/2) + '" y="-30" width="' + pw + '" height="60" rx="12" fill="' + pFill + '" fill-opacity="' + pOp + '" stroke="rgba(255,255,255,0.22)" stroke-width="1.5"/>'
        + '<text x="0" y="10" text-anchor="middle" font-family="' + SANS + '" font-size="30" font-weight="700" letter-spacing="1" fill="#FFFFFF">' + esc(lbl) + '</text></g>';
    }

    // Bottom face-safe WORD-BY-WORD DARK CHARCOAL STICKER TILES (exact #31 "[STUFF] [THEM] [IN]"!)
    var capD = 'ST:' + activeStep;
    if (raw) {
      var mStart = (moment && (moment.t0 != null ? moment.t0 : moment.start)) || 0;
      var mAge = Math.max(0, t - mStart);
      var words = raw.toUpperCase().split(/\s+/).filter(Boolean).slice(0, 6);
      // Split into 1 or 2 clean rows of sticker tiles
      var rows = words.length <= 3 ? [words] : [words.slice(0, Math.ceil(words.length / 2)), words.slice(Math.ceil(words.length / 2))];
      var yStart = rows.length === 1 ? 1420 : 1372;
      var globalIdx = 0;
      var sigs = [];
      for (var r = 0; r < rows.length; r++) {
        var rWords = rows[r];
        var tileWidths = rWords.map(function (w) { return Math.round(measureW(w, 46, 700, SANS) + 38); });
        var gap = 14;
        var totalW = tileWidths.reduce(function (a, b) { return a + b; }, 0) + gap * (rWords.length - 1);
        var xCur = Math.round(540 - totalW / 2);
        var yRow = yStart + r * 86;
        for (var k = 0; k < rWords.length; k++) {
          var w = rWords[k];
          var tw = tileWidths[k];
          var wAge = mAge - globalIdx * 0.065;
          if (wAge > 0) {
            var sc = 0.72 + 0.28 * spring(wAge, 0.24);
            var isKey = (globalIdx === words.length - 1);
            var bg = isKey ? '#EF4444' : '#18181B';
            var cx = xCur + tw / 2;
            svg += '<g transform="translate(' + cx.toFixed(1) + ',' + yRow + ') scale(' + sc.toFixed(3) + ')" filter="url(#sh)">'
              + '<rect x="' + (-tw/2).toFixed(1) + '" y="-36" width="' + tw + '" height="72" rx="12" fill="' + bg + '" fill-opacity="0.92" stroke="rgba(255,255,255,0.18)" stroke-width="1.5"/>'
              + '<text x="0" y="16" text-anchor="middle" font-family="' + SANS + '" font-size="46" font-weight="700" letter-spacing="0.8" fill="#FFFFFF">' + esc(w) + '</text></g>';
            sigs.push(globalIdx + ':' + Math.round(sc * 20));
          }
          xCur += tw + gap;
          globalIdx++;
        }
      }
      capD += '|' + raw + '@' + sigs.join(',');
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return capD || 'IDLE';
  };
  window.occupiedRects = function () { return [{ slot: 'hook', x: 100, y: 180, w: 880, h: 72 }, { slot: 'caption', x: 80, y: 1320, w: 920, h: 190 }]; };
})();
