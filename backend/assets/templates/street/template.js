/* 街头快剪，1080×1920。画面在模板外铺到 y=1290，这里从 1290 起是实心黑。
   中文一次一句，整句在关键词上变黄绿，并做 120ms 的 1.18→1 弹出。
   英文原句留在这一句换走之前，关键词从说到的那一刻起保持黄绿。
   左下单行「名字：短话题」跟着当前说话人。renderFrame(t) 只由 t 决定。 */
(function () {
  var data = null;
  var seenPhrase = null;

  function esc(value) {
    return String(value).replace(/[&<>]/g, function (ch) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;"}[ch];
    });
  }

  function clamp(value, lo, hi) {
    return Math.max(lo, Math.min(hi, value));
  }

  function ease(p) {
    p = clamp(p, 0, 1);
    return 1 - Math.pow(1 - p, 3);
  }

  function units(text) {
    var total = 0;
    for (var i = 0; i < text.length; i++) total += text.charCodeAt(i) > 255 ? 1 : 0.55;
    return total;
  }

  function clipTopic(text) {
    var out = "";
    for (var i = 0; i < text.length; i++) {
      if (units(out + text.charAt(i)) > 12) break;
      out += text.charAt(i);
    }
    return out.replace(/[，。、！？：；,.!?\s]+$/g, "");
  }

  function topicText() {
    if (data.topic) return String(data.topic);
    var lines = data.title_lines || [];
    var raw = String(lines[0] || "").trim();
    var names = (data.speakers || []).map(function (person) { return person.name; }).filter(Boolean);
    for (var guard = 0; guard < 4; guard++) {
      var changed = false;
      for (var i = 0; i < names.length; i++) {
        var marked = [names[i] + "：", names[i] + ":"];
        for (var m = 0; m < marked.length; m++) {
          if (raw.indexOf(marked[m]) >= 0) {
            raw = raw.split(marked[m]).join("");
            changed = true;
          }
        }
      }
      if (!changed) break;
    }
    return clipTopic(raw.trim());
  }

  function moments() {
    if (data.moments && data.moments.length) return data.moments;
    var words = data.words || [];
    var built = [];
    for (var i = 0; i < words.length; i++) {
      var word = words[i];
      var t0 = word.start_frame / data.fps;
      var t1 = word.end_frame / data.fps;
      built.push({
        t0: t0,
        t1: t1,
        speaker: word.speaker || "",
        zh: [{s: String(word.text || "").replace(/\n/g, ""), t0: t0, t1: t1, key: !!word.emphasis, acc: false}],
        en: enFrom(String(word.original || ""), t0, t1, String(word.emphasis || ""))
      });
    }
    return built;
  }

  function enFrom(original, t0, t1, emphasis) {
    var tokens = String(original || "").split(/\s+/).filter(Boolean);
    if (!tokens.length) return [];
    var weights = tokens.map(function (token) { return Math.max(token.length, 1); });
    var total = weights.reduce(function (sum, weight) { return sum + weight; }, 0);
    var span = Math.max(t1 - t0, 0.05);
    var cursor = t0;
    return tokens.map(function (token, index) {
      var dur = span * weights[index] / total;
      var row = {w: token, t0: cursor, t1: cursor + dur, key: enKey(token, emphasis)};
      cursor += dur;
      return row;
    });
  }

  function enKey(token, emphasis) {
    if (!emphasis) return false;
    var leaf = String(token).replace(/[^A-Za-z0-9]+/g, "").toLowerCase();
    var folded = String(emphasis).replace(/[^A-Za-z0-9]+/g, "").toLowerCase();
    if (leaf && folded && (leaf === folded || (leaf.length >= 3 && folded.indexOf(leaf) >= 0) || (folded.length >= 3 && leaf.indexOf(folded) >= 0))) return true;
    var digits = String(emphasis).match(/\d+/g) || [];
    for (var i = 0; i < digits.length; i++) if (digits[i] && String(token).indexOf(digits[i]) >= 0) return true;
    return false;
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
    var list = moment.zh || [];
    for (var i = 0; i < list.length; i++) if (t >= list[i].t0) best = list[i];
    return best || list[0] || null;
  }

  function speakerName(moment) {
    if (moment && moment.speaker) return moment.speaker;
    var lines = (data.title_lines || []).join("");
    var list = data.speakers || [];
    for (var i = 0; i < list.length; i++) {
      if (list[i].name && lines.indexOf(list[i].name) >= 0) return list[i].name;
    }
    return (list[0] && list[0].name) || "";
  }

  function labelFor(moment) {
    var topic = topicText();
    var name = speakerName(moment);
    if (name && topic) return name + "：" + topic;
    return name || topic;
  }

  function lineWidth(node) {
    // A block stretched by the caption column reports the column, not the glyphs.
    var display = node.style.display;
    node.style.display = "inline-block";
    var width = node.scrollWidth;
    node.style.display = display;
    return width;
  }

  function fit(node, start, floor, step, limit, face) {
    if (!node || typeof node.scrollWidth !== "number") return;
    // A fallback face is wider than Anton. Shrinking against it freezes the line too small.
    if (face && document.fonts && document.fonts.check && !document.fonts.check(face)) {
      node.style.fontSize = start + "px";
      return;
    }
    var size = start;
    node.style.fontSize = size + "px";
    while (size > floor && lineWidth(node) > limit) {
      size -= step;
      node.style.fontSize = size + "px";
    }
  }

  function enState(t, word) {
    if (t >= word.t1) return " past";
    if (t >= word.t0) return " now";
    return "";
  }

  function enHtml(moment, t) {
    var html = "";
    var list = moment.en || [];
    for (var i = 0; i < list.length; i++) {
      var word = list[i];
      html += (i ? " " : "") + '<span class="w' + (word.key ? " k" : "") + enState(t, word) + '">' + esc(word.w) + "</span>";
    }
    return html;
  }

  function numberHtml(t) {
    var number = data.number;
    if (!number) return "";
    var index = Math.max(0, Math.floor(t * data.fps + 1e-4));
    var step = -1;
    if (index >= number.start_frame && index < number.end_frame) {
      var span = Math.max(1, number.end_frame - number.start_frame);
      var steps = number.steps || 6;
      var delta = index - number.start_frame;
      step = 0;
      while (step + 1 < steps && (step + 1) * span <= delta * steps) step += 1;
    } else if (index >= number.end_frame && index < (number.hold_frame || number.end_frame)) {
      step = (number.steps || 6) - 1;
    }
    if (step < 0) return "";
    return esc(String(Math.round(number.value * (step + 1) / (number.steps || 6)))) + esc(number.unit || "");
  }

  function paintStickers(t) {
    var host = document.getElementById("stickers");
    var index = Math.max(0, Math.floor(t * data.fps + 1e-4));
    var html = "";
    var shown = 0;
    var stickers = data.stickers || [];
    for (var i = 0; i < stickers.length && shown < 2; i++) {
      var item = stickers[i];
      if (index < item.start_frame || index >= item.end_frame) continue;
      html += '<div class="sticker" style="left:' + (item.x || 40) + "px;top:" + (item.y || 80) + 'px">' + esc(item.text || "") + "</div>";
      shown += 1;
    }
    host.innerHTML = html;
  }

  window.setData = function (fill) {
    data = fill || {};
    seenPhrase = null;
  };

  window.renderFrame = function (t) {
    var total = Number(data.T) > 0 ? Number(data.T) : 1;
    var moment = momentAt(t);
    var phrase = moment ? phraseAt(moment, t) : null;
    var zh = document.getElementById("zh");
    var en = document.getElementById("en");
    var cap = document.getElementById("cap");
    if (!phrase && !(data.words || []).length) {
      var fallback = (data.title_lines || []).join("");
      phrase = fallback ? {s: topicText() || fallback, t0: 0, key: false} : null;
    }
    if (phrase) {
      cap.style.display = "";
      var text = String(phrase.s || "").replace(/[，。、！？：；,.!?]+$/g, "");
      if (!seenPhrase || seenPhrase.s !== phrase.s || seenPhrase.t0 !== phrase.t0) {
        seenPhrase = phrase;
        zh.innerHTML = esc(text);
        zh.className = phrase.key ? "k" : "";
      }
      fit(zh, 100, 70, 4, 1000, '700 100px "Noto Sans CJK SC"');
      var popped = ease((t - (phrase.t0 || 0)) / 0.12);
      zh.style.transform = "scale(" + (1.18 + (1 - 1.18) * popped).toFixed(3) + ")";
      en.innerHTML = moment ? enHtml(moment, t) : "";
      fit(en, 36, 24, 2, 1000, "36px Anton");
    } else {
      cap.style.display = "none";
      zh.innerHTML = "";
      zh.className = "";
      en.innerHTML = "";
      seenPhrase = null;
    }
    var label = labelFor(moment);
    var topic = document.getElementById("topic");
    topic.textContent = label;
    topic.style.display = label ? "" : "none";
    document.getElementById("num").innerHTML = numberHtml(t);
    paintStickers(t);
    var width = (100 * clamp(t / total, 0, 1)).toFixed(2);
    document.getElementById("prog").style.width = width + "%";
    return [text || "", zh.className, en.innerHTML, label, width].join("|");
  };

  window.occupiedRects = function (t) {
    var rects = [];
    var moment = momentAt(t);
    var phrase = moment ? phraseAt(moment, t) : null;
    if (!phrase && !(data.words || []).length && (data.title_lines || []).length) phrase = {s: topicText()};
    if (phrase) rects.push({slot: "subtitle", x: 30, y: 1331, w: 1020, h: 93});
    if (moment && moment.en && moment.en.length) rects.push({slot: "source", x: 30, y: 1449, w: 1020, h: 32});
    if (labelFor(moment)) rects.push({slot: "hook", x: 40, y: 1812, w: 1000, h: 65});
    if (numberHtml(t)) rects.push({slot: "number", x: 40, y: 80, w: 360, h: 84});
    var index = Math.max(0, Math.floor(t * (data.fps || 30) + 1e-4));
    var shown = 0;
    var stickers = data.stickers || [];
    for (var i = 0; i < stickers.length && shown < 2; i++) {
      var item = stickers[i];
      if (index < item.start_frame || index >= item.end_frame) continue;
      rects.push({slot: "sticker", x: item.x || 40, y: item.y || 80, w: 120, h: 72});
      shown += 1;
    }
    return rects;
  };
})();
