/* GTA VI Creator Pack transparent SVG overlay renderer (1080x1920 @ 30fps).
   Faithful pixel-level port of GTA-VI-Creator-Pack/source/reference.js for live video compositing:
   the game & camera rectangles remain transparent so FFmpeg's real video shines through;
   all atmosphere gradients, brand headers, titles, camera frames, animated event cards,
   captions, and tickers render deterministically from (fill, tSeconds). */
(function (global) {
  'use strict';

  var esc = function (v) {
    return String(v || '').replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[c];
    });
  };
  var box = function (x, y, w, h, c, more) {
    return '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '" fill="' + c + '" ' + (more || '') + '/>';
  };
  var path = function (d, fill, more) {
    return '<path d="' + d + '" fill="' + fill + '" ' + (more || '') + '/>';
  };
  var line = function (x1, y1, x2, y2, c, w) {
    return '<path d="M' + x1 + ' ' + y1 + 'L' + x2 + ' ' + y2 + '" fill="none" stroke="' + c + '" stroke-width="' + (w || 2) + '"/>';
  };
  var textEl = function (x, y, s, size, f, c, attrs) {
    return '<text x="' + x + '" y="' + y + '" font-family="' + f + '" font-size="' + size + '" fill="' + c + '" ' + (attrs || '') + '>' + esc(s) + '</text>';
  };
  var round = function (x, y, r, c) {
    return '<circle cx="' + x + '" cy="' + y + '" r="' + r + '" fill="' + c + '"/>';
  };
  var svgBox = function (name, r, nw, nh, contents) {
    if (!r) return '';
    return '<svg id="' + name + '" x="' + r[0] + '" y="' + r[1] + '" width="' + r[2] + '" height="' + r[3] + '" viewBox="0 0 ' + nw + ' ' + nh + '" preserveAspectRatio="xMinYMid meet" overflow="hidden">' + contents + '</svg>';
  };
  var abs = function (name, inner) { return '<g id="' + name + '">' + inner + '</g>'; };
  var track = function (x, y, s, c, size, ls) {
    return textEl(x, y, s, size || 24, 'PackSans', c || '#ffffff', 'letter-spacing="' + (ls || 3) + '"');
  };
  var dots = '<pattern id="dots" width="10" height="10" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.5" fill="#F2EFE8" opacity=".28"/></pattern>';

  function gradient(id, stops) {
    var out = '<linearGradient id="' + id + '" x2="0%" y2="100%">';
    for (var i = 0; i < stops.length; i++) {
      out += '<stop offset="' + stops[i][0] + '%" stop-color="' + stops[i][1] + '" stop-opacity="' + stops[i][2] + '"/>';
    }
    return out + '</linearGradient>';
  }

  function globe(cx, cy, r, c) {
    var s = '<g transform="translate(' + cx + ' ' + cy + ') rotate(-18)" fill="none" stroke="' + c + '" stroke-width="3"><circle r="' + r + '"/>';
    var rx = [0.39, 0.75];
    for (var i = 0; i < rx.length; i++) s += '<ellipse rx="' + (r * rx[i]) + '" ry="' + r + '"/>';
    var ys = [-0.51, 0, 0.51];
    for (var j = 0; j < ys.length; j++) {
      var k = ys[j];
      var dx = r * Math.sqrt(1 - k * k);
      s += line(-dx, r * k, dx, r * k, c, 2);
    }
    return s + '</g>';
  }

  function sun(x, y, r, c) {
    var s = path('M' + (x - r) + ' ' + y + 'a' + r + ' ' + r + ' 0 0 1 ' + (2 * r) + ' 0Z', c);
    for (var i = 0; i < 3; i++) s += line(x - r * (1 - i * 0.2), y + 8 + i * 8, x + r * (1 - i * 0.2), y + 8 + i * 8, c, 3);
    return s;
  }

  function stripes(x, y, c, n, sc) {
    n = n || 3;
    sc = sc || 1;
    var inner = '';
    for (var i = 0; i < n; i++) inner += path('M' + (i * 20) + ' 0h11l-12 27h-11z', c);
    return '<g transform="translate(' + x + ' ' + y + ') scale(' + sc + ')">' + inner + '</g>';
  }

  function ruler(x, y, w, c) {
    var s = line(x, y, x + w, y, c, 1);
    for (var i = 0; i < 33; i++) s += line(x + (i * w) / 32, y, x + (i * w) / 32, y + (i % 4 ? 7 : 15), c, i % 4 ? 1 : 2);
    return s;
  }

  function matteOverlay(t, g, layout) {
    // Only paint non-game matte accents (paper header for wasted, broadcast bars for news).
    // The game & camera rects stay transparent so FFmpeg's video plane shows through.
    var s = '';
    if (t.key === 'wasted') {
      var topH = layout === 'full' ? 180 : Math.max(440, g[1]);
      s += box(0, 0, 1080, topH, t.paper) + box(0, 0, 1080, 12, t.accent);
    }
    if (t.key === 'news') {
      s += box(0, 0, 1080, 18, t.accent) + box(0, 20, 1080, 6, t.secondary);
    }
    return s;
  }

  function environment(t, g) {
    var accent = t.accent, key = t.key, s = '';
    if (g[1] === 0) {
      s += box(0, 0, 1080, 560, key === 'wasted' ? 'url(#lightTop)' : 'url(#darkTop)');
      var footY = Math.min(920, g[3] - 500);
      s += box(0, footY, 1080, Math.max(340, g[3] - footY), 'url(#shadeFoot)');
    } else {
      s += box(0, g[1] + g[3] - 190, 1080, 190, 'url(#gameFade)') + line(0, g[1], 1080, g[1], accent, 5);
    }
    if (key === 'sunset') {
      var arcs = '';
      for (var i = 0; i < 14; i++) {
        arcs += path('M-100 ' + (1730 + i * 12) + ' Q245 ' + (1515 + i * 13) + ' 555 ' + (1755 + i * 10) + ' T1180 ' + (1630 + i * 14), 'none', 'stroke="' + (i % 4 === 0 ? accent : '#956078') + '" stroke-width="' + (i % 4 === 0 ? 2 : 1) + '"');
      }
      s += '<g opacity=".59">' + arcs + '</g>' + sun(905, 1675, 42, accent);
    } else if (key === 'wasted') {
      s += box(0, 1650, 1080, 270, 'url(#dots)');
      var wave = 'M62 1728h235l12 -6 9 10 12 -17 12 21 13 -39 10 52 12 -36 12 17h43l10 -10 12 13 14 -52 10 69 11 -126 14 144 13 -87 13 56 10 -25 14 18 10 -11h36l10 -9 12 12 17 -17 16 19 16 -8h218';
      s += path(wave, 'none', 'stroke="' + accent + '" stroke-width="3"') + ruler(60, 1795, 960, '#696763');
    } else {
      s += '<g opacity=".23">' + globe(920, 1900, 286, t.secondary) + '</g>';
      for (var k = 0; k < 5; k++) s += line(0, 1658 + k * 34, 1080, 1658 + k * 34, '#25435A', 1);
      s += box(72, 1701, 44, 7, accent) + box(120, 1701, 95, 7, t.secondary) + box(219, 1701, 146, 7, '#3B596D');
    }
    return s;
  }

  function brand(t, r) {
    var accent = t.accent, paper = t.paper, ink = t.ink, key = t.key, s = '';
    if (key === 'sunset') {
      s = round(12, 20, 8, accent) + track(38, 30, 'LIVE   /   COASTAL DRIVE', paper, 23, 3.5) + line(0, 55, 823, 55, paper, 2)
        + textEl(-2, 195, 'VICE CITY', 184, 'PackSlant', paper) + sun(743, 106, 37, accent)
        + '<g transform="rotate(-7 593 183)">' + textEl(420, 234, 'Sunset', 108, 'PackSerif', accent) + '</g>';
      return svgBox('brand', r, 828, 260, s);
    }
    if (key === 'wasted') {
      s = stripes(12, 10, accent, 3, 0.86) + track(78, 34, 'REPLAY DEPT.', ink, 24, 3.2) + track(612, 34, 'INCIDENT LOG', ink, 19, 1.8) + ruler(0, 58, 828, '#595753');
      return svgBox('brand', r, 828, 82, s);
    }
    s = box(0, 0, 161, 45, accent) + textEl(15, 32, '●  LIVE', 24, 'PackSans', ink) + track(185, 32, 'LOCAL BROADCAST', paper, 22, 2.5)
      + globe(770, 90, 49, t.secondary) + textEl(0, 140, 'LEONIDA', 110, 'PackBlack', paper) + textEl(-4, 218, 'NEWS', 109, 'PackSlant', accent)
      + line(236, 206, 828, 206, t.secondary, 3) + line(241, 216, 828, 216, t.secondary, 1);
    return svgBox('brand', r, 828, 230, s);
  }

  function meter(x, y, c) {
    var hs = [10, 17, 7, 25, 30, 17, 9, 20, 12];
    var s = '<g>';
    for (var i = 0; i < hs.length; i++) s += box(x + i * 8, y - hs[i] / 2, 4, hs[i], c);
    return s + '</g>';
  }

  function cameraFrame(t, r) {
    var x = r[0], y = r[1], w = r[2], h = r[3], accent = t.accent, paper = t.paper, key = t.key;
    var s = box(x, y, w, h, 'none', 'stroke="' + paper + '" stroke-width="4"');
    if (key === 'sunset') s += line(x + 10, y + 8, x + w - 10, y + 8, accent, 3) + path('M' + (x + 5) + ' ' + (y + h - 37) + 'v32h38', 'none', 'stroke="' + accent + '" stroke-width="7"');
    if (key === 'wasted') s += box(x, y, 12, 48, accent) + box(x + w - 46, y + h - 8, 46, 8, accent);
    if (key === 'news') s += box(x, y, 68, 6, accent) + box(x, y + h - 34, w, 34, t.ink) + track(x + 9, y + h - 10, 'HOST CAM', paper, 15, 2);
    return s;
  }

  function eventLayer(t, r, fx, label, loc, phase) {
    if (!fx || phase <= 0 || !r) return '';
    var s = '';
    if (fx === 'coast-pass') {
      s = box(0, 13, 524, 62, t.ink, 'fill-opacity=".92" rx="31"') + box(1, 14, 522, 60, 'none', 'stroke="' + t.accent + '" stroke-width="2" rx="30"') + sun(37, 43, 12, t.accent) + track(67, 52, label || 'COAST PASS', t.paper, 24, 2.8) + line(276, 28, 276, 60, t.accent, 2) + textEl(296, 53, loc || '海岸漫游', 25, 'PackSans', t.paper);
      return svgBox('event', r, 560, 86, '<g opacity="' + phase.toFixed(3) + '">' + s + '</g>');
    }
    if (fx === 'impact-hold') {
      s = path('M20 12H801L780 148H0Z', t.ink) + stripes(57, 30, t.accent, 3, 0.75) + textEl(95, 127, label || 'WASTED', 135, 'PackSlant', t.accent) + path('M717 38h47l-5 9h-47zm-7 16h47l-5 9h-47z', t.accent);
      return svgBox('event', r, 810, 158, '<g opacity="' + phase.toFixed(3) + '">' + s + '</g>');
    }
    s = path('M0 0H567L539 73H0Z', t.accent) + stripes(30, 22, t.ink, 2, 0.83) + textEl(80, 56, label || 'BREAKING', 56, 'PackSlant', t.ink) + line(329, 14, 329, 59, t.ink, 2) + textEl(351, 50, '突发快讯', 30, 'PackSans', t.ink);
    return svgBox('event', r, 570, 74, '<g opacity="' + phase.toFixed(3) + '">' + s + '</g>');
  }

  var measureCtx = document.createElement('canvas').getContext('2d');
  function textWidth(s, f, sz) {
    measureCtx.font = sz + 'px ' + f;
    return measureCtx.measureText(s).width;
  }
  function fitFont(s, f, start, maxW) {
    return Math.min(start, (start * maxW) / Math.max(1, textWidth(s, f, start)));
  }

  function titleLayer(t, r, textStr, layout) {
    if (!r || !textStr) return '';
    var x = r[0], y = r[1], w = r[2], h = r[3];
    var en = /^[\x20-\x7e]+$/.test(textStr);
    var f = en ? 'PackBlack' : 'PackSans';
    var c = t.key === 'wasted' && (layout === 'split' || layout === 'desk') && y < 440 ? t.ink : t.paper;
    var sz = fitFont(textStr, f, en ? 132 : 82, w - 7);
    var baseline = y + (h + sz * 0.73) / 2;
    return abs('title', textEl(x, baseline, textStr, sz, f, c, en ? '' : 'stroke="' + c + '" stroke-width="1.2" paint-order="stroke"'));
  }

  function captionLayer(t, r, textStr, host, cam) {
    if (!r || !textStr) return '';
    var x = r[0], y = r[1], w = r[2], h = r[3], accent = t.accent, paper = t.paper;
    var a = '', top, maxSize, label = (host || 'HOST').toUpperCase() + '   /   ' + (cam ? 'HOST MIC' : 'VOICE');
    if (h > 165) {
      a += line(x, y + 1, x + w, y + 1, accent, 2) + meter(x + 1, y + 39, accent) + track(x + 96, y + 48, label, paper, 20, 2.2);
      top = y + 74;
      maxSize = 52;
    } else {
      a += box(x, y + 5, 5, h - 10, accent) + track(x + 23, y + 31, label, accent, 18, 2.0);
      top = y + 42;
      maxSize = 46;
    }
    var left = h > 165 ? x : x + 23;
    var avail = w - (left - x);
    var rows = String(textStr).split('\n').slice(0, 2);
    var size = (y + h - top) / (rows.length * 1.22);
    for (var i = 0; i < rows.length; i++) size = Math.min(size, fitFont(rows[i], 'PackSans', maxSize, avail - 6));
    size = Math.max(24, size);
    for (var j = 0; j < rows.length; j++) a += textEl(left, top + size * (1.02 + j * 1.24), rows[j], size, 'PackSans', paper);
    return abs('caption', a);
  }

  function tickerLayer(t, r, textStr) {
    if (!r || !textStr || r[3] < 64) return '';
    var a = box(0, 0, 828, 72, t.paper) + box(0, 0, 176, 72, t.accent) + textEl(20, 45, '交通简报', 29, 'PackSans', t.ink) + textEl(197, 46, textStr, fitFont(textStr, 'PackSans', 31, 608), 'PackSans', t.ink);
    return svgBox('ticker', r, 828, 72, a);
  }

  function activeEvent(cp, frameIndex) {
    var list = (cp && cp.events) || [];
    for (var i = 0; i < list.length; i++) {
      var ev = list[i];
      var d = frameIndex - ev.frame;
      var total = ev.enter + ev.hold + ev.exit;
      if (d >= 0 && d < total) {
        var phase = Math.max(0, Math.min(1, (d + 1) / Math.max(1, ev.enter), (total - d) / Math.max(1, ev.exit)));
        return { ev: ev, phase: phase };
      }
    }
    return null;
  }

  function mount(defaultTheme, defaultLayout) {
    var state = {};
    var root = document.getElementById('stage');

    window.setData = function (fill) {
      state = fill || {};
    };

    window.renderFrame = function (tSeconds) {
      var t = Number(tSeconds) || 0;
      var fps = state.fps || 30;
      var frameIndex = Math.floor(t * fps + 1e-4);
      var cp = state.creator_pack || {};
      var theme = cp.theme || defaultTheme;
      var layoutId = cp.layout_id || defaultLayout.id;
      var slots = cp.slots || defaultLayout.slots;
      var g = slots.game || [0, 0, 1080, 1920];
      var cam = Boolean(cp.camera_active && slots.camera);

      var titleStr = (state.title_lines || []).join(' ').trim();
      var moment = global.ACTemplate ? global.ACTemplate.momentAt(state, t) : null;
      var capText = '';
      if (moment && moment.zh) {
        var parts = [];
        for (var i = 0; i < moment.zh.length; i++) {
          if (moment.zh[i] && moment.zh[i].s) parts.push(moment.zh[i].s);
        }
        capText = (global.ACTemplate ? global.ACTemplate.twoLines(parts, state.audience_language) : parts).join('\n');
      }
      var host = cp.host || (state.guest && state.guest.name) || 'HOST';
      var loc = cp.location || state.kicker || '';
      var tickStr = cp.ticker || '';
      var amp = cp.reduced_motion ? 0 : (cp.strength !== undefined ? cp.strength : 1);

      var act = activeEvent(cp, frameIndex);
      var evSvg = '';
      var evDigest = 'none';
      if (act && slots.event) {
        var r = slots.event.slice();
        if (act.ev.effect === 'news-flash') r[0] -= (1 - act.phase) * 32 * amp;
        if (act.ev.effect === 'coast-pass') r[1] += (1 - act.phase) * 12 * amp;
        evSvg = eventLayer(theme, r, act.ev.effect, act.ev.label, loc, act.phase);
        evDigest = act.ev.id + ':' + act.phase.toFixed(2);
      }

      var camMaskDef = '';
      var atmAttrs = '';
      if (cam && slots.camera) {
        var cr = slots.camera;
        camMaskDef = '<mask id="atmMask"><rect x="0" y="0" width="1080" height="1920" fill="#ffffff"/>'
          + '<rect x="' + cr[0] + '" y="' + cr[1] + '" width="' + cr[2] + '" height="' + cr[3] + '" fill="#000000"/></mask>';
        atmAttrs = ' mask="url(#atmMask)"';
      }

      var defs = gradient('darkTop', [[0, theme.ink, 0.75], [56, theme.ink, 0.57], [100, theme.ink, 0]])
        + gradient('lightTop', [[0, theme.paper, 1], [50, theme.paper, 1], [100, theme.paper, 0]])
        + gradient('shadeFoot', [[0, theme.ink, 0], [39, theme.ink, 0.68], [70, theme.ink, 0.96], [100, theme.ink, 1]])
        + gradient('gameFade', [[0, theme.ink, 0], [100, theme.ink, 0.66]])
        + dots + camMaskDef;

      var body = abs('matte-overlay', matteOverlay(theme, g, layoutId))
        + '<g id="atmosphere"' + atmAttrs + '>' + environment(theme, g) + '</g>';
      if (theme.key === 'wasted' && g[1] === 0 && slots.brand) {
        body += box(0, 0, 1080, slots.brand[1] + slots.brand[3] + 5, theme.paper, 'opacity=".94"');
      }
      body += brand(theme, slots.brand) + titleLayer(theme, slots.title, titleStr, layoutId);
      if (cam) body += abs('camera-frame', cameraFrame(theme, slots.camera));
      body += evSvg;
      body += captionLayer(theme, slots.caption, capText, host, cam);
      body += tickerLayer(theme, slots.ticker, tickStr);

      root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920"><defs>' + defs + '</defs>' + body + '</svg>';
      return [theme.key, layoutId, titleStr, capText, evDigest, tickStr, cam ? '1' : '0'].join('|');
    };

    window.occupiedRects = function (tSeconds) {
      var cp = state.creator_pack || {};
      var slots = cp.slots || defaultLayout.slots;
      var out = [];
      ['brand', 'title', 'caption', 'ticker'].forEach(function (k) {
        var r = slots[k];
        if (r) out.push({ slot: k, x: r[0], y: r[1], w: r[2], h: r[3] });
      });
      var frameIndex = Math.floor((Number(tSeconds) || 0) * (state.fps || 30) + 1e-4);
      if (activeEvent(cp, frameIndex) && slots.event) {
        var er = slots.event;
        out.push({ slot: 'event', x: er[0], y: er[1], w: er[2], h: er[3] });
      }
      return out;
    };
  }

  global.GTACreatorPack = { mount: mount };
})(window);
