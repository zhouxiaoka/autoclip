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
    var kicker = (state.kicker || '').trim();
    var titleText = (state.title_lines || []).join(' ').trim();
    var mAge = Math.max(0, t - ((moment && moment.start) || 0));
    var rev = blurReveal(mAge, 0.28);

    var svg = '<defs>'
      + '<filter id="soft" x="-20%" y="-20%" width="140%" height="140%">'
      + '<feGaussianBlur in="SourceGraphic" stdDeviation="' + rev.blur.toFixed(2) + '" result="bl"/>'
      + '<feDropShadow dx="0" dy="4" stdDeviation="10" flood-color="#000" flood-opacity="0.58"/></filter>'
      + '<filter id="ksh" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="2" stdDeviation="8" flood-color="#000" flood-opacity="0.5"/></filter>'
      + '</defs>';

    var headD = '';
    if (kicker || (t < 2.2 && titleText)) {
      var topStr = kicker || titleText;
      var kAlpha = easeOutCubic(t / 0.45);
      svg += '<text x="540" y="198" text-anchor="middle" font-family="' + SERIF + '" font-style="italic" font-size="42" letter-spacing="1.5" fill="#FFFFFF" fill-opacity="' + (0.86 * kAlpha).toFixed(2) + '" filter="url(#ksh)">' + esc(topStr) + '</text>';
      headD = topStr + '@' + Math.round(kAlpha * 10);
    }

    var capD = '';
    if (raw) {
      var sz = 70;
      var lines = wrapLines(raw, 800, sz, 400, SERIF, 2);
      var y0 = lines.length === 1 ? 1235 : 1198;
      svg += '<g transform="translate(0,' + rev.dy.toFixed(1) + ')" opacity="' + rev.alpha.toFixed(2) + '" filter="url(#soft)">';
      for (var i = 0; i < lines.length; i++) {
        var isItalic = (i === 1);
        svg += '<text x="540" y="' + (y0 + i * 78) + '" text-anchor="middle" font-family="' + SERIF + '" font-style="' + (isItalic ? 'italic' : 'normal') + '" font-size="' + sz + '" letter-spacing="0.5" fill="#FFFFFF" fill-opacity="0.98">' + esc(lines[i]) + '</text>';
      }
      svg += '</g>';
      capD = raw + '@' + rev.step;
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return headD + '||' + capD;
  };
  window.occupiedRects = function () { return [{ slot: 'caption', x: 120, y: 1140, w: 840, h: 180 }]; };
})();
