/* 街头快剪叠加层。人物留在上半，字幕落在下半的暗处。
   大字中文里，packaging.emphasis 命中的词用黄绿标出；英文原句在其下，同一词同样标出。
   左下是色条 + 说话人：话题，角色做小字署名。安全区来自 fill.safe 或 fill.safe_area。
   renderFrame(t) 只由 t 决定。线描贴纸最多两枚。字幕一次只显示当前这一屏。 */
(function () {
  var data = null;
  var SAFE = {
    xiaohongshu: {top: 96, bottom: 168, left: 48, right: 48},
    douyin: {top: 72, bottom: 220, left: 36, right: 36},
    tiktok: {top: 80, bottom: 210, left: 36, right: 36},
    instagram_reels: {top: 88, bottom: 200, left: 40, right: 40},
    youtube_shorts: {top: 72, bottom: 180, left: 36, right: 36}
  };

  function frameIndex(t) {
    return Math.max(0, Math.floor(t * data.fps + 1e-4));
  }

  function insets() {
    return data.safe || SAFE[data.safe_area] || SAFE.xiaohongshu;
  }

  function visibleStickers(index) {
    var shown = [];
    var stickers = data.stickers || [];
    for (var i = 0; i < stickers.length; i++) {
      var item = stickers[i];
      if (index >= item.start_frame && index < item.end_frame) shown.push(item);
      if (shown.length >= 2) break;
    }
    return shown;
  }

  function labelAt() {
    var lines = data.title_lines || [];
    var people = data.speakers || [];
    var name = people.length ? String(people[0].name || "") : "";
    var role = people.length ? String(people[0].role || "") : "";
    var topic = [lines[0] || "", lines[1] || ""].filter(Boolean);
    if (name && topic.length) return {a: name + "：" + topic.join(""), b: role};
    return {a: lines[0] || "", b: lines[1] || ""};
  }

  function stateAt(t) {
    var index = frameIndex(t);
    var words = data.words || [];
    var word = -1;
    for (var i = 0; i < words.length; i++) {
      if (index >= words[i].start_frame && index < words[i].end_frame) {
        word = i;
        break;
      }
    }
    var chunk = word;
    var step = -1;
    var number = data.number;
    if (number && index >= number.start_frame && index < number.end_frame) {
      var span = Math.max(1, number.end_frame - number.start_frame);
      var steps = number.steps || 6;
      var delta = index - number.start_frame;
      step = 0;
      while (step + 1 < steps && (step + 1) * span <= delta * steps) step += 1;
    } else if (number && index >= number.end_frame && index < (number.hold_frame || number.end_frame)) {
      step = (number.steps || 6) - 1;
    }
    var stickers = visibleStickers(index).map(function (item) { return item.id; }).join(",");
    var label = labelAt();
    var origin = word >= 0 ? String(words[word].original || "") : "";
    return {
      hash: [label.a, label.b, String(chunk), origin, String(step), stickers].join("|"),
      chunk: chunk,
      word: word,
      step: step,
      stickers: visibleStickers(index)
    };
  }

  function escapeText(value) {
    return String(value).replace(/[&<>]/g, function (ch) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;"}[ch];
    });
  }

  function highlight(text, phrase) {
    var raw = String(text || "");
    var flat = raw.replace(/\n/g, "");
    var at = -1;
    var len = phrase ? String(phrase).length : 0;
    if (phrase && len) {
      var needle = String(phrase);
      at = flat.indexOf(needle);
      if (at < 0) {
        var found = flat.toLowerCase().indexOf(needle.toLowerCase());
        if (found >= 0) at = found;
      }
    }
    var html = "";
    var count = 0;
    var open = false;
    for (var i = 0; i < raw.length; i++) {
      var ch = raw.charAt(i);
      if (ch === "\n") {
        html += "<br>";
        continue;
      }
      if (at >= 0 && count === at) {
        html += "<em>";
        open = true;
      }
      html += escapeText(ch);
      count += 1;
      if (open && count === at + len) {
        html += "</em>";
        open = false;
      }
    }
    if (open) html += "</em>";
    return html;
  }

  function paint(state) {
    var box = insets();
    var label = labelAt();
    var bar = document.getElementById("titlebar");
    bar.style.top = "auto";
    bar.style.left = box.left + "px";
    bar.style.right = box.right + "px";
    bar.style.bottom = box.bottom + "px";
    document.getElementById("line-a").textContent = label.a;
    document.getElementById("line-b").textContent = label.b;
    document.getElementById("tick").style.display = (label.a || label.b) ? "block" : "none";
    var num = document.getElementById("num");
    num.style.top = (480 + box.top - 96) + "px";
    num.style.left = box.left + "px";
    if (state.step < 0 || !data.number) {
      num.innerHTML = "";
    } else {
      var shown = Math.round(data.number.value * (state.step + 1) / (data.number.steps || 6));
      num.innerHTML = escapeText(String(shown)) + "<small>" + escapeText(data.number.unit || "") + "</small>";
    }
    var host = document.getElementById("stickers");
    host.innerHTML = "";
    for (var s = 0; s < state.stickers.length && s < 2; s++) {
      var node = document.createElement("div");
      node.className = "sticker";
      node.style.top = (state.stickers[s].y || 360) + "px";
      node.style.left = (state.stickers[s].x || 480) + "px";
      node.textContent = state.stickers[s].text || "";
      host.appendChild(node);
    }
    var item = state.word >= 0 ? (data.words || [])[state.word] : null;
    var origin = item && item.original ? String(item.original) : "";
    var sourceLines = origin ? Math.min(2, origin.split("\n").length) : 0;
    var labelH = label.a && label.b ? 52 : ((label.a || label.b) ? 28 : 0);
    var sourceH = sourceLines ? sourceLines * 20 + 8 : 0;
    var sourceBottom = box.bottom + labelH + 96;
    var sub = document.getElementById("sub");
    var source = document.getElementById("source");
    sub.style.left = box.left + "px";
    sub.style.right = box.right + "px";
    sub.style.bottom = (sourceBottom + sourceH) + "px";
    source.style.left = box.left + "px";
    source.style.right = box.right + "px";
    source.style.bottom = sourceBottom + "px";
    if (!item) {
      sub.innerHTML = "";
      source.innerHTML = "";
      return;
    }
    sub.innerHTML = highlight(item.text, item.emphasis) + " ";
    source.innerHTML = origin ? highlight(origin, item.emphasis) : "";
  }

  window.setData = function (fill) {
    data = fill;
  };

  window.renderFrame = function (t) {
    var state = stateAt(t);
    paint(state);
    return state.hash;
  };

  window.occupiedRects = function (t) {
    var state = stateAt(t);
    var box = insets();
    var rects = [];
    var label = labelAt();
    var labelH = label.a && label.b ? 52 : ((label.a || label.b) ? 28 : 0);
    if (labelH) rects.push({slot: "hook", x: box.left, y: 1280 - box.bottom - labelH, w: 720 - box.left - box.right, h: labelH});
    if (state.step >= 0) rects.push({slot: "number", x: box.left, y: 480 + box.top - 96, w: 360, h: 84});
    for (var s = 0; s < state.stickers.length && s < 2; s++) {
      rects.push({slot: "sticker", x: state.stickers[s].x || 480, y: state.stickers[s].y || 360, w: 120, h: 72});
    }
    if (state.chunk >= 0) {
      var item = (data.words || [])[state.chunk];
      var lines = String(item.text || "").split("\n").length;
      var subH = Math.min(2, lines) * 60;
      var origin = String(item.original || "");
      var sourceH = origin ? Math.min(2, origin.split("\n").length) * 20 + 8 : 0;
      var sourceBottom = box.bottom + labelH + 96;
      rects.push({slot: "subtitle", x: box.left, y: 1280 - (sourceBottom + sourceH) - subH, w: 720 - box.left - box.right, h: subH});
      if (sourceH) rects.push({slot: "source", x: box.left, y: 1280 - sourceBottom - sourceH, w: 720 - box.left - box.right, h: sourceH});
    }
    return rects;
  };
})();
