(function () {
  'use strict';
  var state = {};
  var root = document.getElementById('stage');
  var mctx = document.createElement('canvas').getContext('2d');
  var SANS = "'ACSpace', Inter, Helvetica, sans-serif";
  var POSTER = "'ACAnton', 'ACBarlow', Impact, sans-serif";
  var SERIF = "'ACInstrument', 'ACPlayfair', Georgia, serif";
  var PLAYFAIR = "'ACPlayfair', Georgia, serif";
  var BRUSH = "'ACCaveat', Georgia, cursive";

  function esc(v) {
    return String(v || '').replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[c];
    });
  }

  function clamp01(x) { return x < 0 ? 0 : (x > 1 ? 1 : x); }
  function easeOutCubic(x) { var p = clamp01(x); return 1 - Math.pow(1 - p, 3); }
  function easeOutBack(x) {
    var p = clamp01(x);
    var c1 = 1.70158, c3 = c1 + 1;
    return 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2);
  }
  function springPop(age, dur) {
    var p = clamp01(age / (dur || 0.24));
    if (p >= 1) return 1;
    return 0.78 + 0.22 * easeOutBack(p);
  }
  function blurReveal(age, dur) {
    var p = easeOutCubic(age / (dur || 0.26));
    return {
      alpha: p,
      blur: Math.max(0, (1 - p) * 7.5),
      dy: (1 - p) * 20,
      step: Math.round(p * 20),
    };
  }

  function measureW(text, sz, weight, family) {
    mctx.font = (weight || 700) + ' ' + sz + 'px ' + (family || SANS);
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

  function wrapLines(text, maxW, sz, weight, family, maxLines) {
    var words = String(text || '').trim().split(/\s+/).filter(Boolean);
    if (!words.length) return [];
    var lines = [];
    var cur = words[0];
    for (var i = 1; i < words.length; i++) {
      var cand = cur + ' ' + words[i];
      if (measureW(cand, sz, weight, family) <= maxW) {
        cur = cand;
      } else {
        lines.push(cur);
        cur = words[i];
        if (maxLines && lines.length >= maxLines - 1) {
          var rest = words.slice(i).join(' ');
          lines.push(rest);
          return lines;
        }
      }
    }
    lines.push(cur);
    return lines;
  }

  window.setData = function (fill) { state = fill || {}; };

  window.renderFrame = function (tSeconds) {
    var t = Number(tSeconds) || 0;
    var lang = state.audience_language || 'en';
    var moment = window.ACTemplate ? window.ACTemplate.momentAt(state, t) : null;
    var raw = cueText(moment, lang);
    var titleText = (state.title_lines || []).join(' ').trim() || 'BATTERY HABITS TESTED';

    var svg = '<defs>'
      + '<filter id="sh" x="-15%" y="-15%" width="130%" height="140%"><feDropShadow dx="0" dy="6" stdDeviation="12" flood-color="#000" flood-opacity="0.42"/></filter>'
      + '</defs>';

    var activeIdx = t < 1.1 ? 0 : (t < 2.2 ? 1 : 2);
    var cols = [
      { label: 'HURTS', bg: '#DC2626', fg: '#FCA5A5' },
      { label: 'NO EFFECT', bg: '#EAB308', fg: '#FDE047' },
      { label: 'HELPS', bg: '#16A34A', fg: '#86EFAC' },
    ];
    var bx = 72, by = 152, colW = 304, gap = 12;
    svg += '<g filter="url(#sh)">';
    for (var i = 0; i < cols.length; i++) {
      var cx = bx + i * (colW + gap);
      var isAct = i === activeIdx;
      var sc = isAct ? 1.03 : 0.96;
      var op = isAct ? '1' : '0.42';
      svg += '<g transform="translate(' + (cx + colW / 2) + ',' + (by + 32) + ') scale(' + sc + ')">'
        + '<rect x="' + (-colW / 2) + '" y="-32" width="' + colW + '" height="64" rx="14" fill="' + cols[i].bg + '" fill-opacity="' + op + '"/>'
        + '<text x="0" y="10" text-anchor="middle" font-family="' + SANS + '" font-size="28" font-weight="700" letter-spacing="1.4" fill="#FFFFFF">' + cols[i].label + '</text></g>';
    }
    svg += '<rect x="190" y="' + (by + 84) + '" width="700" height="52" rx="26" fill="#0F1115" fill-opacity="0.82"/>'
      + '<text x="540" y="' + (by + 119) + '" text-anchor="middle" font-family="' + SANS + '" font-size="26" font-weight="700" letter-spacing="1" fill="#FFFFFF">' + esc(titleText) + '</text>'
      + '</g>';

    var activeCol = cols[activeIdx];
    var mAge = Math.max(0, t - ((moment && moment.start) || 0));
    var psc = springPop(mAge, 0.22);
    var capD = '';
    if (raw) {
      var csz = 44;
      var cw = measureW(raw, csz, 700, SANS);
      if (cw > 820) { csz = Math.max(30, Math.floor((csz * 820) / cw)); cw = measureW(raw, csz, 700, SANS); }
      var pw = Math.min(900, Math.round(cw + 56));
      var ph = Math.round(csz * 1.75);
      var py = 1480;
      svg += '<g transform="translate(540,' + py + ') scale(' + psc.toFixed(3) + ')" filter="url(#sh)">'
        + '<rect x="' + (-pw / 2) + '" y="' + (-ph / 2) + '" width="' + pw + '" height="' + ph + '" rx="16" fill="#0F1115" fill-opacity="0.9" stroke="' + activeCol.bg + '" stroke-width="3"/>'
        + '<text x="0" y="' + Math.round(csz * 0.34) + '" text-anchor="middle" font-family="' + SANS + '" font-size="' + csz + '" font-weight="700" fill="' + activeCol.fg + '">' + esc(raw) + '</text>'
        + '</g>';
      capD = raw + '@' + activeIdx + ':' + Math.round(psc * 40);
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return titleText + '||' + capD;
  };
  window.occupiedRects = function () { return [{ slot: 'hook', x: 72, y: 152, w: 936, h: 140 }, { slot: 'caption', x: 90, y: 1430, w: 900, h: 100 }]; };
})();
