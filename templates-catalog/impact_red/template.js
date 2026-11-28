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
    var titleLines = (state.title_lines || []).filter(Boolean);

    var svg = '<defs>'
      + '<radialGradient id="vg" cx="50%" cy="50%" r="65%"><stop offset="0%" stop-color="#000" stop-opacity="0.28"/><stop offset="100%" stop-color="#000" stop-opacity="0.58"/></radialGradient>'
      + '<linearGradient id="botSc" x1="0%" y1="0%" x2="0%" y2="100%"><stop offset="0%" stop-color="#000" stop-opacity="0"/><stop offset="100%" stop-color="#000" stop-opacity="0.6"/></linearGradient>'
      + '<filter id="sh" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="8" stdDeviation="14" flood-color="#000" flood-opacity="0.65"/></filter>'
      + '</defs>';

    var vars = state.vars || {};
    var accent = (typeof vars.accent_color === 'string' && vars.accent_color) ? vars.accent_color : '#EF4444';
    var hookAccent = (typeof vars.accent_color === 'string' && vars.accent_color) ? vars.accent_color : '#C81E1E';
    var scaleMap = { S: 0.86, M: 1.0, L: 1.15 };
    var fScale = scaleMap[String(vars.font_scale || 'M').toUpperCase()] || 1.0;

    // Phase 1 (0..1.35s): Background is genuinely Gaussian-blurred by FFmpeg -> giant red/white slam dead-center
    if (t < 1.35 && titleLines.length) {
      var words = titleLines.join(' ').trim().split(/\s+/).slice(0, 3);
      var fadeOut = t > 1.15 ? clamp01((1.35 - t) / 0.2) : 1;
      svg += '<rect x="0" y="0" width="1080" height="1920" fill="url(#vg)" opacity="' + fadeOut.toFixed(2) + '"/>';
      var baseY = 825;
      var steps = [];
      for (var i = 0; i < words.length; i++) {
        var age = t - i * 0.10;
        if (age < 0) continue;
        var sc = 0.80 + 0.20 * spring(age, 0.24);
        var al = easeOutCubic(age / 0.14) * fadeOut;
        var w = words[i].toUpperCase();
        var isRed = (i === 1) || /\d/.test(w);
        var sz = Math.round((isRed ? 176 : 128) * fScale);
        var ww = measureW(w, sz, 400, POSTER);
        if (ww > 880) sz = Math.max(72, Math.floor((sz * 880) / ww));
        var y = baseY + i * 144;
        svg += '<g transform="translate(540,' + y + ') scale(' + sc.toFixed(3) + ')" opacity="' + al.toFixed(2) + '">'
          + '<text x="0" y="0" text-anchor="middle" font-family="' + POSTER + '" font-size="' + sz + '" letter-spacing="2" fill="' + (isRed ? hookAccent : '#FFFFFF') + '" filter="url(#sh)">' + esc(w) + '</text></g>';
        steps.push(Math.round(sc * 40));
      }
      root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
      return 'BLURHOOK:' + words.join('|') + ':' + steps.join(',');
    }

    // Phase 2 (1.35s+): Video is sharp -> STRICT FACE-SAFE lower-third (y=1375), mixed-size word stagger, accent emphasis!
    var capD = '';
    if (raw) {
      svg += '<rect x="0" y="1220" width="1080" height="700" fill="url(#botSc)"/>';
      var mStart = Math.max(1.35, (moment && moment.start) || 1.35);
      var mAge = Math.max(0, t - mStart);
      var words = raw.split(/\s+/).filter(Boolean);
      var focalIdx = pickFocalIndex(words);

      // Render as clean 1-line or 2-line face-safe kinetic block with word-by-word spring + accent focal word
      var mid = words.length > 3 ? Math.ceil(words.length / 2) : words.length;
      var rowLists = words.length > 3 ? [words.slice(0, mid), words.slice(mid)] : [words];
      var y0 = rowLists.length === 1 ? 1400 : 1355;
      var wCounter = 0;
      for (var r = 0; r < rowLists.length; r++) {
        var rowW = rowLists[r];
        var totalW = 0;
        var specs = [];
        for (var k = 0; k < rowW.length; k++) {
          var isFoc = (wCounter === focalIdx);
          var fsz = Math.round((isFoc ? 72 : 52) * fScale);
          var fam = isFoc ? POSTER : SANS;
          var wt = isFoc ? 400 : 700;
          var txt = isFoc ? rowW[k].toUpperCase() : rowW[k];
          var tw = measureW(txt, fsz, wt, fam);
          specs.push({ txt: txt, isFoc: isFoc, fsz: fsz, fam: fam, wt: wt, tw: tw, idx: wCounter });
          totalW += tw + (k > 0 ? 18 : 0);
          wCounter++;
        }
        var xCur = Math.round(540 - totalW / 2);
        var yLine = y0 + r * 78;
        for (var m = 0; m < specs.length; m++) {
          var sp = specs[m];
          var wage = Math.max(0, mAge - sp.idx * 0.055);
          var wp = easeOutQuint(wage / 0.22);
          var wsc = sp.isFoc ? (0.82 + 0.18 * spring(wage, 0.24)) : (0.94 + 0.06 * wp);
          var cx = xCur + sp.tw / 2;
          svg += '<g transform="translate(' + cx.toFixed(1) + ',' + (yLine + (1 - wp) * 14).toFixed(1) + ') scale(' + wsc.toFixed(3) + ')" opacity="' + wp.toFixed(2) + '">'
            + '<text x="0" y="0" text-anchor="middle" font-family="' + sp.fam + '" font-size="' + sp.fsz + '" font-weight="' + sp.wt + '" letter-spacing="' + (sp.isFoc ? '1.5' : '-0.5') + '" fill="' + (sp.isFoc ? accent : '#FFFFFF') + '" filter="url(#sh)">' + esc(sp.txt) + '</text></g>';
          xCur += sp.tw + 18;
        }
      }
      capD = 'BODY:' + raw + '@' + Math.round(easeOutCubic(mAge / 0.3) * 20);
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return capD || 'IDLE';
  };
  window.occupiedRects = function () { return [{ slot: 'caption', x: 90, y: 1290, w: 900, h: 190 }]; };
})();
