/* 电影，1080×1920。上下留宽银幕黑边。大标题只在封面上，成片字幕停在下边里。
   renderFrame(t) 只由 t 决定。 */
(function () {
  var data = null;

  function esc(value) {
    return String(value).replace(/[&<>]/g, function (ch) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;"}[ch];
    });
  }

  function moments() {
    if (data.moments && data.moments.length) return data.moments;
    var words = data.words || [];
    var built = [];
    for (var i = 0; i < words.length; i++) {
      var word = words[i];
      var t0 = word.start_frame / (data.fps || 30);
      var t1 = word.end_frame / (data.fps || 30);
      built.push({
        t0: t0,
        t1: t1,
        zh: [{s: String(word.text || "").replace(/\n/g, ""), t0: t0, t1: t1}],
        en: String(word.original || "").split(/\s+/).filter(Boolean).map(function (token) { return {w: token}; })
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

  function phraseAt(moment, t) {
    var best = null;
    var list = (moment && moment.zh) || [];
    for (var i = 0; i < list.length; i++) if (t >= list[i].t0) best = list[i];
    return best;
  }

  function enHtml(moment) {
    var list = (moment && moment.en) || [];
    var html = "";
    for (var i = 0; i < list.length; i++) html += (i ? " " : "") + esc(list[i].w || "");
    return html;
  }

  window.setData = function (fill) {
    data = fill || {};
  };

  window.renderFrame = function (t) {
    var moment = momentAt(t);
    var phrase = moment ? phraseAt(moment, t) : null;
    var zh = document.getElementById("zh");
    var en = document.getElementById("en");
    var text = "";
    if (phrase) {
      text = String(phrase.s || "").replace(/[，。、！？：；,.!?]+$/g, "");
      zh.textContent = text;
      en.innerHTML = enHtml(moment);
    } else {
      zh.textContent = "";
      en.innerHTML = "";
    }
    var hook = document.getElementById("h-l");
    if (hook) hook.innerHTML = "";
    return [text, en.innerHTML].join("|");
  };

  window.occupiedRects = function (t) {
    var moment = momentAt(t);
    var phrase = moment ? phraseAt(moment, t) : null;
    if (!phrase) return [];
    return [{slot: "subtitle", x: 80, y: 1668, w: 920, h: 100}];
  };
})();
