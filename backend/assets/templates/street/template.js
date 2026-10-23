/* 街头快剪，1080×1920。画面在模板外铺到 y=1290，这里从 1290 起是实心黑。
   中文一次一句，字号是字幕而不是标题，整句不再铺成黄绿大字。弹出仍是 120ms 的 1.18→1。
   英文原句留在这一句换走之前，关键词从说到的那一刻起保持黄绿。
   左下只留当前说话人的名字。短话题是封面标题，不烧进成片。renderFrame(t) 只由 t 决定。 */
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

  function topicText() {
    // The short topic is the cover title. The bottom label keeps the speaker name only.
    return "";
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

  function hostName(name) {
    var text = String(name || "");
    return {"主持人": 1, "嘉宾": 1, "采访者": 1, "记者": 1, "host": 1, "interviewer": 1, "guest": 1}[text] ||
      {"主持人": 1, "嘉宾": 1, "采访者": 1, "记者": 1, "host": 1, "interviewer": 1, "guest": 1}[text.toLowerCase()];
  }

  function displayName(name) {
    name = String(name || "");
    if (!name) return "";
    var zh = (data.audience_language || "") === "zh";
    var latin = /[A-Za-z]/.test(name) && !/[\u4e00-\u9fff]/.test(name);
    if (!zh || !latin) return name;
    var guests = (data.speakers || []).map(function (person) { return person.name; }).filter(function (item) {
      return item && /[\u4e00-\u9fff]/.test(item) && !hostName(item);
    });
    // One Chinese guest replaces Jensen Huang. Several Chinese guests: do not guess.
    // No Chinese form: Sam Altman stays. The cover title is not burned in that slot.
    if (guests.length === 1) return guests[0];
    return guests.length ? "" : name;
  }

  function speakerName(moment) {
    // A name needs a cue that names its speaker. With no caption on screen (captions off, or
    // between cues) nothing says who is talking, and the guest is not stamped on the host.
    return moment ? displayName(moment.speaker || "") : "";
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
    var stroke = 0;
    if (window.getComputedStyle) {
      stroke = parseFloat(getComputedStyle(node).webkitTextStrokeWidth) || 0;
    }
    // The stroke is centered on the outline, so the full width hangs outside the glyphs.
    return width + stroke;
  }

  function faceReady(node, face) {
    if (!face || !document.fonts || !document.fonts.check) return true;
    // check(font) is false while any unicode-range file in the family is still pending.
    // Anton and Instrument Serif ship in slices, so pass the glyphs actually on the line.
    var sample = String(node && node.textContent || "").replace(/\s+/g, " ").trim().slice(0, 32) || "Ag";
    try {
      if (document.fonts.check(face, sample)) return true;
    } catch (error) { /* older check() takes one argument */ }
    return !!document.fonts.check(face);
  }

  function ellipsisText(node, limit, gauge) {
    var box = gauge || node;
    var text = String(node.textContent || "").replace(/…$/, "");
    var parts = text.split(/\s+/).filter(Boolean);
    if (parts.length > 1) {
      while (parts.length > 1 && lineWidth(box) > limit) {
        parts.pop();
        node.textContent = parts.join(" ") + "…";
      }
    }
    text = String(node.textContent || "");
    var guard = 0;
    while (lineWidth(box) > limit && text.replace(/…$/, "").length > 1 && guard < 80) {
      text = text.replace(/…$/, "").slice(0, -1);
      node.textContent = text + "…";
      guard += 1;
    }
  }

  function trimTo(node, limit) {
    if (!node || typeof node.scrollWidth !== "number") return;
    if (lineWidth(node) <= limit) return;
    var kids = node.children;
    if (kids && kids.length && node.removeChild) {
      while (kids.length > 1 && lineWidth(node) > limit) node.removeChild(kids[kids.length - 1]);
      if (lineWidth(node) > limit && kids.length) ellipsisText(kids[kids.length - 1], limit, node);
      return;
    }
    ellipsisText(node, limit);
  }

  function fit(node, start, floor, step, limit, face) {
    if (!node || typeof node.scrollWidth !== "number") return;
    // A fallback face is wider than Anton. Shrinking against it freezes the line too small.
    if (!faceReady(node, face)) {
      node.style.fontSize = start + "px";
      return;
    }
    var size = start;
    node.style.fontSize = size + "px";
    while (size > floor && lineWidth(node) > limit) {
      size -= step;
      node.style.fontSize = size + "px";
    }
    trimTo(node, limit);
  }

  function enState(t, word) {
    if (t >= word.t1) return " past";
    if (t >= word.t0) return " now";
    return "";
  }

  function enForPhrase(moment, phrase) {
    // The English line is the words being spoken with this Chinese phrase, not the start of the sentence.
    var list = (moment && moment.en) || [];
    if (!phrase) return [];
    var out = [];
    for (var i = 0; i < list.length; i++) {
      var word = list[i];
      if (word.t1 > phrase.t0 + 1e-3 && word.t0 < phrase.t1 - 1e-3) out.push(word);
    }
    return out;
  }

  function enShown(moment, t) {
    // The whole English sentence stays up across its Chinese phrases, one line of it at a time,
    // chosen by when its words are spoken. Old fills without screens follow the phrase.
    var list = (moment && moment.en) || [];
    var screens = moment && moment.en_screens;
    if (!screens || !screens.length) return enForPhrase(moment, phraseAt(moment, t));
    var pick = screens[0];
    for (var i = 0; i < screens.length; i++) {
      var first = list[screens[i][0]];
      if (first && first.t0 <= t + 0.03) pick = screens[i];
    }
    return list.slice(pick[0], pick[1]);
  }

  function enHtml(moment, t) {
    var list = enShown(moment, t);
    if (!list.length) return "";
    var html = "";
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

  function titleSticker() {
    // Opening title cards belong on the cover, not in the clip.
    return "";
  }

  window.renderFrame = function (t) {
    var moment = momentAt(t);
    var phrase = moment ? phraseAt(moment, t) : null;
    var zh = document.getElementById("zh");
    var en = document.getElementById("en");
    var cap = document.getElementById("cap");
    var text = "";
    var scale = "";
    if (phrase) {
      cap.style.display = "";
      text = String(phrase.s || "").replace(/[，。、！？：；,.!?]+$/g, "");
      // Rebuild from the phrase so a trim on a fallback face cannot stick.
      seenPhrase = phrase;
      zh.innerHTML = esc(text);
      // The whole sentence in yellow read as a title card. Keywords stay on the English line.
      zh.className = "";
      // Caption size. Shrink only when the phrase would not fit the 1000px line.
      fit(zh, 48, 32, 2, 1000, '700 48px "Noto Sans CJK SC"');
      // The hash carries the scale itself: a popping flag made capture keep the 1.18 frame for the whole ease.
      var popped = ease((t - (phrase.t0 || 0)) / 0.12);
      scale = (1.18 + (1 - 1.18) * popped).toFixed(3);
      zh.style.transform = "scale(" + scale + ")";
      en.innerHTML = moment ? enHtml(moment, t) : "";
      if (en.innerHTML) fit(en, 36, 24, 2, 1000, "36px Anton");
    } else {
      cap.style.display = "none";
      zh.innerHTML = "";
      zh.className = "";
      en.innerHTML = "";
      seenPhrase = null;
    }
    var label = labelFor(moment);
    var sticker = titleSticker(t);
    var topic = document.getElementById("topic");
    topic.textContent = label;
    topic.style.display = label ? "" : "none";
    var title = document.getElementById("title-hook");
    if (title) {
      title.textContent = sticker;
      // Stylesheet display:none wins if the inline value is cleared.
      title.style.display = sticker ? "block" : "none";
    }
    document.getElementById("num").innerHTML = numberHtml(t);
    paintStickers(t);
    return [text || "", zh.className, en.innerHTML, label, scale, numberHtml(t), sticker].join("|");
  };

  window.occupiedRects = function (t) {
    var rects = [];
    var moment = momentAt(t);
    var phrase = moment ? phraseAt(moment, t) : null;
    if (phrase) rects.push({slot: "subtitle", x: 30, y: 1326, w: 1020, h: 56});
    // Captions-off hook sits in the black band under the picture, not on the face (head zone ends at 1290).
    if (titleSticker(t)) rects.push({slot: "title", x: 40, y: 1360, w: 1000, h: 192});
    if (moment && phrase && enShown(moment, t).length) rects.push({slot: "source", x: 30, y: 1406, w: 1020, h: 36});
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
