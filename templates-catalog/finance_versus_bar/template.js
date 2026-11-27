(function () {
  'use strict';
  var state = {};
  var root = document.getElementById('stage');
  var SANS = "'PingFang SC', 'Noto Sans SC', 'ACSpace', sans-serif";
  var COND = "'ACBarlow', 'PingFang SC', sans-serif";
  function esc(v) {
    return String(v || '').replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[c];
    });
  }
  function clamp01(x) { return x < 0 ? 0 : (x > 1 ? 1 : x); }
  function cueText(m, lang) {
    if (!m || !m.zh || !m.zh.length) return '';
    return m.zh.map(function (x) { return x.s || ''; }).join(lang === 'en' ? ' ' : '').trim();
  }
  window.setData = function (fill) { state = fill || {}; };
  window.renderFrame = function (tSeconds) {
    var t = Number(tSeconds) || 0;
    var lang = state.audience_language || 'zh';
    var lines = (state.title_lines || []).filter(Boolean);
    var leftLbl = lines[0] || (lang === 'en' ? 'OLD WAY' : '传统做法');
    var rightLbl = lines[1] || (lang === 'en' ? 'NEW WAY' : '新范式');

    var list = (window.ACTemplate && window.ACTemplate.moments) ? window.ACTemplate.moments(state) : [];
    var idx = 0;
    var moment = null;
    for (var i = 0; i < list.length; i++) {
      var a = list[i].t0 != null ? list[i].t0 : list[i].start;
      var b = list[i].t1 != null ? list[i].t1 : list[i].end;
      if (t >= a && t < b) { idx = i; moment = list[i]; break; }
    }
    var rightActive = (idx % 2) === 1;
    var p = clamp01(t / 0.35);
    var leftBar = rightActive ? 140 : Math.round(180 + 140 * p);
    var rightBar = rightActive ? Math.round(220 + 120 * p) : 160;

    var parts = [
      '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">',
      '<g opacity="' + (0.2 + 0.8 * p).toFixed(3) + '">',
      '<rect x="76" y="148" width="928" height="164" rx="22" fill="#14151A" fill-opacity="0.82" stroke="#FFFFFF" stroke-opacity="0.16" stroke-width="2"/>',
      // Left side
      '<rect x="92" y="164" width="424" height="132" rx="14" fill="' + (!rightActive ? '#FF5C5C' : '#FFFFFF') + '" fill-opacity="' + (!rightActive ? '0.18' : '0.04') + '"/>',
      '<text x="118" y="218" font-family="' + SANS + '" font-size="34" font-weight="800" fill="' + (!rightActive ? '#FF8080' : '#9CA3AF') + '">' + esc(leftLbl.slice(0, 12)) + '</text>',
      '<rect x="118" y="246" width="372" height="14" rx="7" fill="#FFFFFF" fill-opacity="0.12"/>',
      '<rect x="118" y="246" width="' + leftBar + '" height="14" rx="7" fill="#FF5C5C"/>',
      // VS badge
      '<circle cx="540" cy="230" r="28" fill="#1E2028" stroke="#FFFFFF" stroke-opacity="0.28" stroke-width="2"/>',
      '<text x="540" y="241" text-anchor="middle" font-family="' + COND + '" font-size="30" fill="#FFFFFF">VS</text>',
      // Right side
      '<rect x="564" y="164" width="424" height="132" rx="14" fill="' + (rightActive ? '#34D399' : '#FFFFFF') + '" fill-opacity="' + (rightActive ? '0.18' : '0.04') + '"/>',
      '<text x="590" y="218" font-family="' + SANS + '" font-size="34" font-weight="800" fill="' + (rightActive ? '#6EE7B7' : '#9CA3AF') + '">' + esc(rightLbl.slice(0, 12)) + '</text>',
      '<rect x="590" y="246" width="372" height="14" rx="7" fill="#FFFFFF" fill-opacity="0.12"/>',
      '<rect x="590" y="246" width="' + rightBar + '" height="14" rx="7" fill="#34D399"/>',
      '</g>'
    ];

    var text = cueText(moment, lang);
    var capD = 'IDLE';
    if (text) {
      capD = text + '_' + idx;
      var fz = text.length > 24 ? 42 : 48;
      parts.push(
        '<text x="540" y="1486" text-anchor="middle" font-family="' + SANS + '" font-size="' + fz + '" font-weight="800" fill="#FFFFFF" stroke="#0B0C10" stroke-width="10" paint-order="stroke" stroke-linejoin="round">' + esc(text) + '</text>'
      );
    }
    parts.push('</svg>');
    root.innerHTML = parts.join('');
    return 'VS_' + capD;
  };
  window.occupiedRects = function () { return []; };
})();
