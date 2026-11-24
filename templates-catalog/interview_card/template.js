/* 访谈卡片. renderFrame(t) depends only on t and the fill. Every visible word comes from the fill:
   series   <- kicker, else issue (model's show · date, or "{guest} 访谈")
   headline <- title_lines (model, per clip)
   guest    <- guest {name, role} (model-identified single guest)
   captions <- moments (transcript + translation); host lines get a localized "Host:" label
   footer   <- excerpt note, plus an AI-translation disclosure only when the captions were translated.
   Fixed labels are localized by audience_language. */
(function () {
  var data = {};
  var HOST_ROLE = /主持|host|interviewer/i;
  var LABELS = {
    zh: {guest: '本段嘉宾 ', host: '主持人：', source: '来源：', excerpt: '节选，有删减', translated: '中英字幕 AI 辅助翻译剪辑'},
    en: {guest: 'Guest: ', host: 'Host: ', source: 'Source: ', excerpt: 'Excerpt, edited', translated: 'AI-assisted translated subtitles'}
  };

  function $(id) { return document.getElementById(id); }
  function labels() { return LABELS[data.audience_language === 'en' ? 'en' : 'zh']; }

  function isHost(name) {
    if (!name) return false;
    var guest = data.guest;
    if (guest && guest.name === name) return false;
    var hosts = data.hosts || [];
    for (var i = 0; i < hosts.length; i++) if (hosts[i] === name) return true;
    var list = data.speakers || [];
    for (var j = 0; j < list.length; j++) {
      if (list[j].name === name) return HOST_ROLE.test(list[j].role || '');
    }
    return false;
  }

  function moments() {
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
        zh: [{s: String(w.text || '').replace(/\n/g, '')}],
        en: String(w.original || '').split(/\s+/).filter(Boolean).map(function (token) { return {w: token}; })
      });
    }
    return built;
  }

  function momentAt(t) {
    var list = moments();
    var found = null;
    for (var i = 0; i < list.length; i++) {
      if (t >= list[i].t0 && t < list[i].t1) found = list[i];
    }
    return found;
  }

  function twoLines(pieces) {
    // At most two lines, breaking at a clause boundary nearest the middle.
    if (pieces.length <= 2) return pieces;
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
    var sep = data.audience_language === 'en' ? ' ' : '';
    return [pieces.slice(0, best).join(sep), pieces.slice(best).join(sep)];
  }

  function zhText(moment) {
    // One clause per line: 「…开发流程，」 / 「那次分享…播放。」
    var parts = moment.zh || [];
    var lines = [];
    for (var i = 0; i < parts.length; i++) {
      var piece = String(parts[i].s || '');
      if (piece) lines.push(piece);
    }
    var text = twoLines(lines).join('\n');
    var label = labels().host;
    if (isHost(moment.speaker) && text.indexOf(label) !== 0) text = label + text;
    return text;
  }

  function enText(moment) {
    if (!data.translated) return '';
    var list = moment.en || [];
    var out = [];
    for (var i = 0; i < list.length; i++) {
      var token = list[i].w || list[i].s || '';
      if (token) out.push(token);
    }
    return out.join(' ');
  }

  window.setData = function (fill) {
    data = fill || {};
    var L = labels();
    var series = String(data.kicker || data.issue || '');
    // The backend fallback issue is "{guest} 访谈"; never show Chinese on an English-audience clip.
    if (data.audience_language === 'en' && /\s*访谈$/.test(series)) series = series.replace(/\s*访谈$/, '') + ' · Interview';
    $('series').textContent = series;
    $('title').textContent = (data.title_lines || []).join('\n');
    var guest = data.guest;
    $('guest').textContent = guest && guest.name ? L.guest + guest.name : '';
    $('role').textContent = guest && guest.role ? guest.role : '';
    // The issue already sits on top; repeat it as the source only when the kicker took the top line.
    $('source').textContent = data.kicker && data.issue ? L.source + data.issue : '';
    $('note').textContent = data.translated ? L.excerpt + ' · ' + L.translated : L.excerpt;
  };

  window.renderFrame = function (t) {
    var moment = momentAt(Number(t) || 0);
    var zh = moment ? zhText(moment) : '';
    var en = moment ? enText(moment) : '';
    $('zh').textContent = zh;
    $('en').textContent = en;
    return zh + '|' + en;
  };

  window.occupiedRects = function () {
    var rects = [];
    ['head', 'subtitle', 'foot'].forEach(function (id) {
      var el = $(id);
      var r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0 && el.textContent.trim()) {
        rects.push({slot: id, x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height)});
      }
    });
    return rects;
  };
})();
