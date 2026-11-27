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

  function animateNumbers(text, p) {
    return String(text || '').replace(/(\d+(?:\.\d+)?)/g, function (m) {
      var val = parseFloat(m);
      var dec = m.indexOf('.') >= 0 ? (m.split('.')[1].length) : 0;
      var cur = val * p;
      return dec > 0 ? cur.toFixed(dec) : String(Math.round(cur));
    });
  }

  window.renderFrame = function (tSeconds) {
    var t = Number(tSeconds) || 0;
    var lang = state.audience_language || 'en';
    var moment = window.ACTemplate ? window.ACTemplate.momentAt(state, t) : null;
    var raw = cueText(moment, lang);
    var titleLines = (state.title_lines || []).filter(Boolean);
    var kicker = (state.kicker || 'LAST 30 DAYS').trim();

    var cardIn = easeOutCubic(t / 0.38);
    var cardDy = (1 - cardIn) * -36;
    var countP = easeOutCubic(Math.max(0, t - 0.15) / 1.15);
    var lineLen = 220;
    var dashOff = Math.round(lineLen * (1 - countP));

    var metricMainRaw = titleLines[0] || '184.4K · $41.2K';
    var metricMain = animateNumbers(metricMainRaw, countP);
    var metricSub = titleLines[1] || 'Organic Growth Snapshot';

    var mAge = Math.max(0, t - ((moment && moment.start) || 0));
    var cRev = blurReveal(mAge, 0.22);

    var svg = '<defs>'
      + '<filter id="cardSh" x="-15%" y="-15%" width="130%" height="140%"><feDropShadow dx="0" dy="14" stdDeviation="20" flood-color="#000" flood-opacity="0.5"/></filter>'
      + '<filter id="txtSh" x="-15%" y="-15%" width="130%" height="140%"><feGaussianBlur in="SourceGraphic" stdDeviation="' + cRev.blur.toFixed(2) + '"/><feDropShadow dx="0" dy="4" stdDeviation="8" flood-color="#000" flood-opacity="0.72"/></filter>'
      + '</defs>';

    var cardY = 148, cardW = 860, cardX = 110, cardH = 200;
    svg += '<g transform="translate(0,' + cardDy.toFixed(1) + ')" opacity="' + cardIn.toFixed(2) + '" filter="url(#cardSh)">'
      + '<rect x="' + cardX + '" y="' + cardY + '" width="' + cardW + '" height="' + cardH + '" rx="24" fill="#0F1117" fill-opacity="0.88" stroke="#FFFFFF" stroke-opacity="0.16" stroke-width="2"/>'
      + '<circle cx="' + (cardX + 42) + '" cy="' + (cardY + 46) + '" r="7" fill="#22C55E"/>'
      + '<text x="' + (cardX + 62) + '" y="' + (cardY + 54) + '" font-family="' + SANS + '" font-size="24" font-weight="700" letter-spacing="2.2" fill="#A1A1AA">' + esc(kicker.toUpperCase()) + '</text>'
      + '<text x="' + (cardX + 38) + '" y="' + (cardY + 122) + '" font-family="' + SANS + '" font-size="54" font-weight="700" fill="#F8FAFC">' + esc(metricMain) + '</text>'
      + '<text x="' + (cardX + 38) + '" y="' + (cardY + 166) + '" font-family="' + SANS + '" font-size="25" font-weight="500" fill="#94A3B8">' + esc(metricSub) + '</text>'
      + '<path d="M735,288 L770,276 L802,282 L838,252 L874,244 L918,214" fill="none" stroke="#22C55E" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="' + lineLen + '" stroke-dashoffset="' + dashOff + '"/>'
      + '</g>';

    var capD = '';
    if (raw) {
      var sz = 48;
      var lines = wrapLines(raw, 860, sz, 700, SANS, 2);
      var y0 = lines.length === 1 ? 1480 : 1445;
      svg += '<g transform="translate(0,' + cRev.dy.toFixed(1) + ')" opacity="' + cRev.alpha.toFixed(2) + '" filter="url(#txtSh)">';
      for (var i = 0; i < lines.length; i++) {
        svg += '<text x="540" y="' + (y0 + i * 62) + '" text-anchor="middle" font-family="' + SANS + '" font-size="' + sz + '" font-weight="700" fill="#F4F1EA">' + esc(lines[i]) + '</text>';
      }
      svg += '</g>';
      capD = raw + '@' + cRev.step;
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return metricMain + ':' + dashOff + '||' + capD;
  };
  window.occupiedRects = function () { return [{ slot: 'hook', x: 110, y: 148, w: 860, h: 200 }, { slot: 'caption', x: 90, y: 1400, w: 900, h: 140 }]; };
})();
