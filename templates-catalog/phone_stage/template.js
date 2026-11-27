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
    var label = ((state.kicker || (state.title_lines || [])[0] || 'MY SPACE').trim()).toUpperCase();
    var lsc = springPop(t, 0.26);
    var mAge = Math.max(0, t - ((moment && moment.start) || 0));
    var rev = blurReveal(mAge, 0.22);

    var fx = 116, fy = 280, fw = 848, fh = 1240, r = 56;
    var cutout = 'M0,0 H1080 V1920 H0 Z '
      + 'M' + (fx + r) + ',' + fy
      + ' H' + (fx + fw - r) + ' Q' + (fx + fw) + ',' + fy + ' ' + (fx + fw) + ',' + (fy + r)
      + ' V' + (fy + fh - r) + ' Q' + (fx + fw) + ',' + (fy + fh) + ' ' + (fx + fw - r) + ',' + (fy + fh)
      + ' H' + (fx + r) + ' Q' + fx + ',' + (fy + fh) + ' ' + fx + ',' + (fy + fh - r)
      + ' V' + (fy + r) + ' Q' + fx + ',' + fy + ' ' + (fx + r) + ',' + fy + ' Z';

    var svg = '<defs><filter id="cr" x="-15%" y="-15%" width="130%" height="140%"><feGaussianBlur in="SourceGraphic" stdDeviation="' + (rev.blur * 0.5).toFixed(2) + '"/></filter></defs>'
      + '<path d="' + cutout + '" fill="#08080A" fill-rule="evenodd"/>'
      + '<rect x="' + fx + '" y="' + fy + '" width="' + fw + '" height="' + fh + '" rx="' + r + '" fill="none" stroke="#FFFFFF" stroke-opacity="0.18" stroke-width="3"/>';

    var lsz = 32;
    var lw = measureW(label, lsz, 700, SANS);
    var lpw = Math.min(720, Math.round(lw + 48));
    svg += '<g transform="translate(540,212) scale(' + lsc.toFixed(3) + ')">'
      + '<rect x="' + (-lpw / 2) + '" y="-30" width="' + lpw + '" height="60" rx="12" fill="#FACC15"/>'
      + '<text x="0" y="11" text-anchor="middle" font-family="' + SANS + '" font-size="' + lsz + '" font-weight="700" letter-spacing="2.5" fill="#09090B">' + esc(label) + '</text></g>';

    var capD = '';
    if (raw) {
      var lines = wrapLines(raw, 860, 40, 600, SANS, 2);
      var y0 = lines.length === 1 ? 1645 : 1615;
      svg += '<g transform="translate(0,' + (rev.dy * 0.6).toFixed(1) + ')" opacity="' + rev.alpha.toFixed(2) + '" filter="url(#cr)">';
      for (var i = 0; i < lines.length; i++) {
        svg += '<text x="540" y="' + (y0 + i * 54) + '" text-anchor="middle" font-family="' + SANS + '" font-size="40" font-weight="600" fill="#F4F4F5">' + esc(lines[i]) + '</text>';
      }
      svg += '</g>';
      capD = raw + '@' + rev.step;
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return label + '||' + capD;
  };
  window.occupiedRects = function () { return [{ slot: 'hook', x: 180, y: 180, w: 720, h: 64 }, { slot: 'caption', x: 90, y: 1580, w: 900, h: 120 }]; };
})();
