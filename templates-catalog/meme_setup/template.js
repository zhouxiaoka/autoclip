/* Meme Setup Banner (Bilibili/Douyin viral comedy & gaming setup style) — 1080x1920 @ 30fps. */
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
    mctx.font = '900 ' + sz + 'px "PingFang SC", "Noto Sans CJK SC", "Helvetica Neue", sans-serif';
    return Math.max(1, mctx.measureText(text).width);
  }

  function wrapLines(text, sz, maxW, maxLines) {
    var clean = String(text || '').trim();
    if (!clean) return [];
    if (measureW(clean, sz) <= maxW) return [clean];
    var words = /\s/.test(clean) ? clean.split(/\s+/) : clean.split('');
    var joiner = /\s/.test(clean) ? ' ' : '';
    var lines = [];
    var cur = '';
    for (var i = 0; i < words.length; i++) {
      var cand = cur ? (cur + joiner + words[i]) : words[i];
      if (cur && measureW(cand, sz) > maxW) {
        lines.push(cur);
        cur = words[i];
        if (lines.length >= maxLines - 1) break;
      } else {
        cur = cand;
      }
    }
    if (cur) lines.push(cur);
    return lines.slice(0, maxLines);
  }

  window.setData = function (fill) {
    state = fill || {};
  };

  window.renderFrame = function (tSeconds) {
    var t = Number(tSeconds) || 0;
    var titleText = (state.title_lines || []).join(' ').trim();
    var kicker = String(state.kicker || '').trim();
    var lang = state.audience_language || 'zh';
    var moment = window.ACTemplate ? window.ACTemplate.momentAt(state, t) : null;

    var svg = '<defs>'
      + '<linearGradient id="botScrim" x2="0" y2="1"><stop offset="0%" stop-color="#000000" stop-opacity="0"/><stop offset="100%" stop-color="#000000" stop-opacity="0.72"/></linearGradient>'
      + '<filter id="sh" x="-10%" y="-10%" width="120%" height="130%"><feDropShadow dx="0" dy="8" stdDeviation="10" flood-color="#000000" flood-opacity="0.38"/></filter>'
      + '</defs>';

    svg += '<rect x="0" y="1220" width="1080" height="700" fill="url(#botScrim)"/>';

    // Top signature bright-yellow rounded setup card (e.g. "当只有你一人打残局 / 听到对面拆包")
    var headDigest = '';
    if (titleText) {
      var sz = 54;
      var rows = wrapLines(titleText, sz, 760, 2);
      if (rows.length === 1 && measureW(rows[0], sz) > 760) {
        sz = Math.max(36, Math.floor((sz * 760) / measureW(rows[0], sz)));
      }
      var maxRowW = 0;
      for (var r = 0; r < rows.length; r++) maxRowW = Math.max(maxRowW, measureW(rows[r], sz));
      var cardW = Math.min(880, Math.max(460, Math.round(maxRowW + 84)));
      var lineH = Math.round(sz * 1.32);
      var cardH = rows.length * lineH + 46;
      var cx = Math.round(540 - cardW / 2);
      var cy = 152;
      svg += '<g filter="url(#sh)">'
        + '<rect x="' + cx + '" y="' + cy + '" width="' + cardW + '" height="' + cardH + '" rx="30" fill="#FFE642"/>';
      for (var j = 0; j < rows.length; j++) {
        var ty = cy + 23 + Math.round((j + 0.5) * lineH + sz * 0.34);
        svg += '<text x="540" y="' + ty + '" text-anchor="middle" font-size="' + sz + '" font-weight="900" fill="#141416">' + esc(rows[j]) + '</text>';
      }
      svg += '</g>';

      // Optional POV / twist tag right below the yellow setup card (e.g. "你以为的：")
      if (kicker) {
        svg += '<text x="' + (cx + 12) + '" y="' + (cy + cardH + 74) + '" font-size="44" font-weight="900" fill="#FFFFFF" stroke="#0C0C10" stroke-width="10" stroke-linejoin="round" paint-order="stroke">' + esc(kicker) + '</text>';
      }
      headDigest = rows.join('/') + '|' + kicker;
    }

    // Punchy lower-third caption with thick black stroke & yellow highlight on punch words
    var capDigest = '';
    if (moment && moment.zh && moment.zh.length) {
      var parts = [];
      for (var i = 0; i < moment.zh.length; i++) {
        if (moment.zh[i] && moment.zh[i].s) parts.push(moment.zh[i].s);
      }
      var raw = parts.join(lang === 'en' ? ' ' : '').trim();
      if (raw) {
        var csz = 62;
        var cw = measureW(raw, csz);
        if (cw > 900) csz = Math.max(38, Math.floor((csz * 900) / cw));
        var hl = esc(raw).replace(
          /(\d+\s*[个秒米倍%]+|残局|爆头|绝杀|翻车|卧槽|离谱|真的|直接|完了|不可能|NO WAY|CLUTCH|OMG)/gi,
          '<tspan fill="#FFE642">$1</tspan>'
        );
        svg += '<text x="540" y="1445" text-anchor="middle" font-size="' + csz + '" font-weight="900" fill="#FFFFFF" stroke="#0A0A0E" stroke-width="' + Math.round(csz * 0.22) + '" stroke-linejoin="round" paint-order="stroke">' + hl + '</text>';
        capDigest = raw;
      }
    }

    root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
    return headDigest + '||' + capDigest;
  };

  window.occupiedRects = function () {
    return [
      { slot: 'hook', x: 100, y: 150, w: 880, h: 220 },
      { slot: 'caption', x: 60, y: 1360, w: 960, h: 140 },
    ];
  };
})();
