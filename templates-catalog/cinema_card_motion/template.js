(function () {
  'use strict';
  var state = {};
  var root = document.getElementById('stage');
  var mctx = document.createElement('canvas').getContext('2d');
  var esc = window.ACTemplate.esc;
  var M = window.ACMotion;
  var FONT = "'PingFang SC', 'Noto Sans SC', 'Helvetica Neue', Arial, sans-serif";

  var card = { x: -46, opacity: 0, sweep: 0 };
  var tl = M.createTimeline()
    .fromTo(card, { x: -42, opacity: 0 }, { x: 0, opacity: 1 }, 0.08, 0.42, 'power4.out')
    .fromTo(card, { sweep: 0 }, { sweep: 1 }, 0.25, 0.65, 'expo.out');

  function measureW(text, sz, wt) {
    mctx.font = (wt || 700) + ' ' + sz + 'px ' + FONT;
    return Math.max(1, mctx.measureText(text).width);
  }

  window.setData = function (fill) { state = fill || {}; };

  window.renderFrame = M.bindTimeline(tl, function (t) {
    var lang = state.audience_language || 'zh';
    var accent = M.getVar(state, 'accent_color', '#34D399');
    var scaleKey = M.getVar(state, 'font_scale', 'M');
    var fScale = ({ S: 0.86, M: 1.0, L: 1.15 })[String(scaleKey).toUpperCase()] || 1.0;

    var parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">'];
    parts.push(M.renderVignette(0.54));

    var lines = (state.title_lines || []).filter(Boolean);
    var head = (lines[0] || state.kicker || '').trim();
    var sub = (lines[1] || state.kicker || '').trim();
    if (head && card.opacity > 0.02) {
      var cw = 760;
      var lineW = Math.round((cw - 56) * card.sweep);
      parts.push('<g transform="translate(' + (160 + card.x).toFixed(1) + ',154)" opacity="' + card.opacity.toFixed(3) + '">');
      parts.push('<rect x="0" y="0" width="' + cw + '" height="114" rx="22" fill="#0F1117" fill-opacity="0.80" stroke="#FFFFFF" stroke-opacity="0.14" stroke-width="2"/>');
      parts.push('<circle cx="34" cy="40" r="6" fill="' + accent + '"/>');
      parts.push('<text x="52" y="48" font-family="' + FONT + '" font-size="30" font-weight="800" fill="#FFFFFF">' + esc(head.slice(0, 22)) + '</text>');
      if (sub && sub !== head) {
        parts.push('<text x="52" y="84" font-family="' + FONT + '" font-size="22" font-weight="500" fill="#A1A1AA">' + esc(sub.slice(0, 32)) + '</text>');
      }
      parts.push('<rect x="28" y="100" width="' + lineW + '" height="4" rx="2" fill="' + accent + '"/>');
      parts.push('</g>');
    }

    var moment = window.ACTemplate.momentAt(state, t);
    var chunks = M.chunkCaption(moment, lang, 4);
    var digest = 'CARD_IDLE_' + Math.round(card.sweep * 20);
    if (chunks.length) {
      var mStart = (moment.t0 != null ? moment.t0 : moment.start) || 0;
      var mEnd = (moment.t1 != null ? moment.t1 : moment.end) || (mStart + 2.0);
      var age = Math.max(0, t - mStart);
      var prog = M.clamp01(age / Math.max(0.2, mEnd - mStart));
      var activeIdx = M.staggerIndex(chunks.length, prog);
      var sep = lang === 'en' ? ' ' : '';
      var full = chunks.join(sep);
      var fz = Math.round((full.length > 20 ? 44 : 52) * fScale);
      var bIn = M.blurIn(age, 0.24, 8);
      var totalW = 0;
      for (var i = 0; i < chunks.length; i++) {
        totalW += measureW(chunks[i], fz, 700) + (i > 0 ? (sep ? measureW(sep, fz, 700) : 6) : 0);
      }
      var xCur = Math.max(70, (1080 - totalW) / 2);
      parts.push('<g transform="translate(0,' + bIn.y.toFixed(1) + ')" opacity="' + bIn.opacity.toFixed(3) + '">');
      for (var j = 0; j < chunks.length; j++) {
        var tok = chunks[j];
        var tw = measureW(tok, fz, 700);
        var col = j === activeIdx ? accent : '#F8FAFC';
        parts.push('<text x="' + xCur.toFixed(1) + '" y="1468" font-family="' + FONT + '" font-size="' + fz + '" font-weight="700" fill="' + col + '" stroke="#090A0F" stroke-width="9" paint-order="stroke" stroke-linejoin="round">' + esc(tok) + '</text>');
        xCur += tw + (sep ? measureW(sep, fz, 700) : 6);
      }
      parts.push('</g>');
      digest = 'CARD_' + full + '_' + activeIdx + '_' + accent + '_' + scaleKey;
    }

    parts.push('</svg>');
    root.innerHTML = parts.join('');
    return digest;
  });

  window.occupiedRects = function () { return [{ slot: 'hook', x: 160, y: 154, w: 760, h: 114 }, { slot: 'caption', x: 70, y: 1400, w: 940, h: 110 }]; };
})();
