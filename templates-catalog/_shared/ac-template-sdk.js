/* AutoClip Shared Template SDK (zero-dependency, deterministic, offline-safe).
   Every function is pure with respect to (data, t) so renderFrame(t) is seek-safe. */
(function (global) {
  'use strict';

  var HOST_ROLE = /主持|host|interviewer/i;
  var LABELS = {
    zh: {
      guest: '本段嘉宾 ',
      host: '主持人：',
      source: '来源：',
      excerpt: '节选，有删减',
      translated: '中英字幕 AI 辅助翻译剪辑'
    },
    en: {
      guest: 'Guest: ',
      host: 'Host: ',
      source: 'Source: ',
      excerpt: 'Excerpt, edited',
      translated: 'AI-assisted translated subtitles'
    }
  };

  function esc(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function labels(data) {
    return LABELS[(data && data.audience_language) === 'en' ? 'en' : 'zh'];
  }

  function moments(data) {
    if (!data) return [];
    if (data.moments && data.moments.length) return data.moments;
    var words = data.words || [];
    var fps = data.fps || 30;
    var built = [];
    for (var i = 0; i < words.length; i++) {
      var w = words[i];
      built.push({
        t0: w.start_frame / fps,
        t1: w.end_frame / fps,
        speaker: w.speaker || '',
        zh: [{ s: String(w.text || '').replace(/\n/g, '') }],
        en: String(w.original || '').split(/\s+/).filter(Boolean).map(function (tok) { return { w: tok }; })
      });
    }
    return built;
  }

  function momentAt(data, t) {
    var sec = Number(t) || 0;
    var list = moments(data);
    var found = null;
    for (var i = 0; i < list.length; i++) {
      if (sec >= list[i].t0 && sec < list[i].t1) found = list[i];
    }
    return found;
  }

  function isHost(data, name) {
    if (!name || !data) return false;
    if (data.guest && data.guest.name === name) return false;
    var hosts = data.hosts || [];
    for (var i = 0; i < hosts.length; i++) if (hosts[i] === name) return true;
    var list = data.speakers || [];
    for (var j = 0; j < list.length; j++) {
      if (list[j].name === name) return HOST_ROLE.test(list[j].role || '');
    }
    return false;
  }

  function twoLines(pieces, audienceLanguage) {
    if (!pieces || pieces.length <= 2) return pieces || [];
    var total = 0;
    for (var i = 0; i < pieces.length; i++) total += pieces[i].length;
    var best = 1;
    var bestGap = Infinity;
    var run = 0;
    for (var k = 1; k < pieces.length; k++) {
      run += pieces[k - 1].length;
      var gap = Math.abs(total / 2 - run);
      if (gap < bestGap) { bestGap = gap; best = k; }
    }
    var sep = audienceLanguage === 'en' ? ' ' : '';
    return [pieces.slice(0, best).join(sep), pieces.slice(best).join(sep)];
  }

  function zhHtml(data, moment, opts) {
    if (!moment) return '';
    opts = opts || {};
    var hlClass = opts.highlightClass || 'hl';
    var parts = moment.zh || [];
    var rendered = [];
    for (var i = 0; i < parts.length; i++) {
      var seg = parts[i];
      var raw = String(seg.s || '');
      if (!raw) continue;
      var safe = esc(raw);
      if (opts.highlight !== false && seg.hl && raw.indexOf(seg.hl) >= 0) {
        var safeHl = esc(seg.hl);
        rendered.push(safe.replace(safeHl, '<span class="' + hlClass + '">' + safeHl + '</span>'));
      } else if (opts.highlight !== false && seg.key) {
        rendered.push('<span class="' + hlClass + '">' + safe + '</span>');
      } else {
        rendered.push(safe);
      }
    }
    var lines = opts.maxLines === 2 ? twoLines(rendered, data && data.audience_language) : rendered;
    var joined = lines.join(opts.joinWith !== undefined ? opts.joinWith : '\n');
    if (opts.hostPrefix && isHost(data, moment.speaker)) {
      var prefix = labels(data).host;
      if (joined.indexOf(prefix) !== 0) joined = esc(prefix) + joined;
    }
    return joined;
  }

  function enText(data, moment, opts) {
    if (!moment) return '';
    opts = opts || {};
    if (opts.onlyTranslated && !(data && data.translated)) return '';
    var list = moment.en || [];
    var out = [];
    for (var i = 0; i < list.length; i++) {
      var tok = list[i] && (list[i].w || list[i].s);
      if (tok) out.push(tok);
    }
    return out.join(' ');
  }

  function activeGloss(data, t) {
    var fps = (data && data.fps) || 30;
    var frame = Math.round((Number(t) || 0) * fps);
    var list = (data && data.gloss) || [];
    for (var i = 0; i < list.length; i++) {
      if (frame >= list[i].start_frame && frame < list[i].end_frame) return list[i];
    }
    return null;
  }

  function occupiedRects(slotIds) {
    var rects = [];
    for (var i = 0; i < slotIds.length; i++) {
      var id = slotIds[i];
      var el = document.getElementById(id);
      if (!el || el.hidden || !el.textContent.trim()) continue;
      var r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) {
        rects.push({ slot: id, x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height) });
      }
    }
    return rects;
  }

  global.ACTemplate = {
    esc: esc,
    labels: labels,
    moments: moments,
    momentAt: momentAt,
    isHost: isHost,
    twoLines: twoLines,
    zhHtml: zhHtml,
    enText: enText,
    activeGloss: activeGloss,
    occupiedRects: occupiedRects
  };

  /* AutoClip Motion Kit v2 (ac-motion-kit): deterministic atomic motion primitives,
     multi-language caption chunking, reusable SVG overlay components, brand variables,
     and optional GSAP paused-timeline bridge. */
  function clamp01(x) { return x < 0 ? 0 : (x > 1 ? 1 : x); }
  function easeOutCubic(x) { var p = clamp01(x); return 1 - Math.pow(1 - p, 3); }
  function easeOutQuint(x) { var p = clamp01(x); return 1 - Math.pow(1 - p, 5); }
  function springPop(age, dur) {
    var p = clamp01((Number(age) || 0) / (dur || 0.28));
    if (p >= 1) return 1;
    return 1 - Math.exp(-7.5 * p) * Math.cos(9.5 * p);
  }
  function blurIn(age, dur, maxBlur) {
    var p = easeOutCubic((Number(age) || 0) / (dur || 0.26));
    return { opacity: p, blur: (1 - p) * (maxBlur || 10), y: (1 - p) * 14 };
  }
  function clipWipe(age, dur) {
    return easeOutQuint((Number(age) || 0) / (dur || 0.3));
  }
  function kineticSlam(age, dur) {
    var p = easeOutQuint((Number(age) || 0) / (dur || 0.22));
    return { scale: 1.32 - 0.32 * p, opacity: clamp01(p * 1.4) };
  }
  function staggerIndex(count, progress) {
    if (!count || count <= 0) return -1;
    return Math.min(count - 1, Math.max(0, Math.floor(clamp01(progress) * count)));
  }
  function getVar(state, key, fallback) {
    if (state && state.vars && state.vars[key] !== undefined && state.vars[key] !== null) {
      return state.vars[key];
    }
    return fallback;
  }
  function chunkCaption(moment, lang, maxCjkChunk) {
    if (!moment || !moment.zh || !moment.zh.length) return [];
    var raw = [];
    for (var i = 0; i < moment.zh.length; i++) {
      if (moment.zh[i] && moment.zh[i].s) raw.push(String(moment.zh[i].s));
    }
    if (raw.length === 1 && /[\u4e00-\u9fff]/.test(raw[0]) && raw[0].length > (maxCjkChunk || 5)) {
      var s = raw[0], step = maxCjkChunk || 4, out = [];
      for (var j = 0; j < s.length; j += step) out.push(s.slice(j, j + step));
      return out;
    }
    if (raw.length === 1 && lang === 'en' && raw[0].indexOf(' ') >= 0) {
      return raw[0].split(/\s+/).filter(Boolean);
    }
    return raw;
  }
  function safeBands() {
    return { topHookY: [130, 360], depthCrownY: [480, 540], lowerCaptionY: [1360, 1620] };
  }
  function renderVignette(strength) {
    var a = clamp01(strength == null ? 0.55 : strength);
    return '<defs><linearGradient id="ac-vig" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0%" stop-color="#000" stop-opacity="0"/>' +
      '<stop offset="100%" stop-color="#000" stop-opacity="' + a.toFixed(2) + '"/>' +
      '</linearGradient></defs><rect x="0" y="1220" width="1080" height="700" fill="url(#ac-vig)"/>';
  }
  function renderGrain(opacity) {
    var op = clamp01(opacity == null ? 0.08 : opacity);
    if (op <= 0.005) return '';
    return '<defs><filter id="ac-grain"><feTurbulence type="fractalNoise" baseFrequency="0.82" numOctaves="2" stitchTiles="stitch"/></filter></defs>' +
      '<rect x="0" y="0" width="1080" height="1920" filter="url(#ac-grain)" opacity="' + op.toFixed(3) + '"/>';
  }
  function bindTimeline(tl, digestFn) {
    global.__acTimeline = tl;
    if (tl && typeof tl.pause === 'function') tl.pause();
    global.renderFrame = function (tSeconds) {
      var t = Number(tSeconds) || 0;
      if (tl && typeof tl.time === 'function') tl.time(t);
      return (typeof digestFn === 'function' ? digestFn(t) : '') || ('TL_' + Math.round(t * 30));
    };
  }

  global.ACMotion = {
    clamp01: clamp01,
    easeOutCubic: easeOutCubic,
    easeOutQuint: easeOutQuint,
    springPop: springPop,
    blurIn: blurIn,
    clipWipe: clipWipe,
    kineticSlam: kineticSlam,
    staggerIndex: staggerIndex,
    getVar: getVar,
    chunkCaption: chunkCaption,
    safeBands: safeBands,
    renderVignette: renderVignette,
    renderGrain: renderGrain,
    bindTimeline: bindTimeline
  };
})(window);
