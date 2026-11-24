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
})(window);
