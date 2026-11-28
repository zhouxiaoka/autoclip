(function () {
  'use strict';
  var state = {};
  var root = document.getElementById('stage');
  var mctx = document.createElement('canvas').getContext('2d');
  var SANS = "'ACSpace', Inter, Helvetica, sans-serif";
  var POSTER = "'ACAnton', Impact, sans-serif";
  var SERIF = "'ACInstrument', Georgia, serif";
  var PLAYFAIR = "'ACPlayfair', Georgia, serif";

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
    // Critically slightly underdamped silky spring
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
    // Pick the strongest focal word (number first, else longest non-stopword)
    var stops = { the:1, a:1, an:1, to:1, of:1, in:1, on:1, for:1, and:1, or:1, is:1, are:1, was:1, that:1, with:1, your:1, you:1, we:1, it:1, into:1, from:1 };
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
    var list = (state && (state.timeline || state.moments)) || [];
    for (var i = 0; i < list.length; i++) {
      if (t >= list[i].start && t < list[i].end) return i;
    }
    return 0;
  }
  window.setData = function (fill) { state = fill || {}; };

  window.renderFrame = function (tSeconds) {
    var t = Number(tSeconds) || 0;
    var lang = state.audience_language || 'en';
    var moment = window.ACTemplate ? window.ACTemplate.momentAt(state, t) : null;
    var raw = cueText(moment, lang);
    var kicker = (state.kicker || '').trim();
    var titleText = (state.title_lines || []).join(' ').trim();

    var svg = '<defs>'
      + '<linearGradient id="bs" x1="0%" y1="0%" x2="0%" y2="100%"><stop offset="0%" stop-color="#000" stop-opacity="0"/><stop offset="100%" stop-color="#000" stop-opacity="0.45"/></linearGradient>'
      + '<filter id="soft" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="4" stdDeviation="11" flood-color="#000" flood-opacity="0.62"/></filter>'
      + '</defs>';

    svg += '<rect x="0" y="1180" width="1080" height="740" fill="url(#bs)"/>';

    // Subtle editorial header above head (y=190)
    if (kicker) {
      var kp = easeOutQuint(t / 0.45);
      svg += '<text x="540" y="196" text-anchor="middle" font-family="' + SANS + '" font-size="22" font-weight="500" letter-spacing="5" fill="#FFFFFF" fill-opacity="' + (0.78 * kp).toFixed(2) + '" filter="url(#soft)">' + esc(kicker.toUpperCase()) + '</text>';
    }

    var vars = state.vars || {};
    var accent = (typeof vars.accent_color === 'string' && vars.accent_color) ? vars.accent_color : '#FFFBEB';
    var fScale = ({ S: 0.86, M: 1.0, L: 1.15 })[String(vars.font_scale || 'M').toUpperCase()] || 1.0;

    // Silky word-by-word mixed typography in face-safe chest/lower-third (y=1330..1420)
    var capD = '';
    if (raw) {
      var mStart = (moment && moment.start) || 0;
      var mAge = Math.max(0, t - mStart);
      var words = raw.split(/\s+/).filter(Boolean);
      var focalIdx = pickFocalIndex(words);
      var mid = words.length > 4 ? Math.ceil(words.length / 2) : words.length;
      var rowLists = words.length > 4 ? [words.slice(0, mid), words.slice(mid)] : [words];
      var y0 = rowLists.length === 1 ? 1385 : 1338;
      var wCounter = 0;
      var steps = [];

      for (var r = 0; r < rowLists.length; r++) {
        var rowW = rowLists[r];
        var totalW = 0, specs = [];
        for (var k = 0; k < rowW.length; k++) {
          var isFoc = (wCounter === focalIdx);
          // Normal words: clean smaller sans/serif; focal word: 1.55x larger Instrument Serif Italic!
          var fsz = Math.round((isFoc ? 84 : 46) * fScale);
          var fam = isFoc ? SERIF : SANS;
          var wt = isFoc ? 400 : 400;
          var tw = measureW(rowW[k], fsz, wt, fam, isFoc);
          specs.push({ txt: rowW[k], isFoc: isFoc, fsz: fsz, fam: fam, wt: wt, tw: tw, idx: wCounter });
          totalW += tw + (k > 0 ? 16 : 0);
          wCounter++;
        }
        var xCur = Math.round(540 - totalW / 2);
        var yLine = y0 + r * Math.round(86 * fScale);
        for (var m = 0; m < specs.length; m++) {
          var sp = specs[m];
          var wage = Math.max(0, mAge - sp.idx * 0.065);
          var wp = easeOutQuint(wage / 0.34);
          var dy = (1 - wp) * 18;
          var sc = sp.isFoc ? (0.90 + 0.10 * spring(wage, 0.32)) : (0.96 + 0.04 * wp);
          var cx = xCur + sp.tw / 2;
          svg += '<g transform="translate(' + cx.toFixed(1) + ',' + (yLine + dy).toFixed(1) + ') scale(' + sc.toFixed(3) + ')" opacity="' + wp.toFixed(2) + '">'
            + '<text x="0" y="0" text-anchor="middle" font-family="' + sp.fam + '" font-style="' + (sp.isFoc ? 'italic' : 'normal') + '" font-size="' + sp.fsz + '" font-weight="' + sp.wt + '" letter-spacing="' + (sp.isFoc ? '0.8' : '0.2') + '" fill="' + (sp.isFoc ? accent : '#FFFFFF') + '" fill-opacity="' + (sp.isFoc ? '1' : '0.92') + '" filter="url(#soft)">' + esc(sp.txt) + '</text></g>';
          xCur += sp.tw + 16;
          steps.push(Math.round(wp * 20));
        }
      }
      capD = raw + ':' + steps.join(',');
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return capD || 'IDLE';
  };
  window.occupiedRects = function () { return [{ slot: 'caption', x: 90, y: 1270, w: 900, h: 190 }]; };
})();
