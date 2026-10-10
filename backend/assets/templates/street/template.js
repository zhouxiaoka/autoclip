/* 街头快剪叠加层。安全区来自 fill.safe 或 fill.safe_area，不把某一平台写死在坐标里。
   renderFrame(t) 只由 t 决定。线描贴纸最多两枚。字幕一次最多三个词。 */
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
    var chunk = word < 0 ? -1 : Math.floor(word / 3);
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
    var lines = data.title_lines || [];
    return {
      hash: [lines[0] || "", lines[1] || "", String(chunk), String(step), stickers].join("|"),
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

  function paint(state) {
    var box = insets();
    var bar = document.getElementById("titlebar");
    bar.style.top = box.top + "px";
    bar.style.left = box.left + "px";
    bar.style.right = box.right + "px";
    var lines = data.title_lines || [];
    document.getElementById("line-a").textContent = lines[0] || "";
    document.getElementById("line-b").textContent = lines[1] || "";
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
    var sub = document.getElementById("sub");
    sub.style.bottom = box.bottom + "px";
    sub.style.left = box.left + "px";
    sub.style.right = box.right + "px";
    if (state.chunk < 0) {
      sub.innerHTML = "";
      return;
    }
    var words = data.words || [];
    var start = state.chunk * 3;
    var html = "";
    for (var w = start; w < Math.min(words.length, start + 3); w++) {
      var text = escapeText(words[w].text);
      if (w === state.word && words[w].emphasis) html += "<em>" + text + "</em> ";
      else html += text + " ";
    }
    sub.innerHTML = html;
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
    var lines = data.title_lines || [];
    if (lines[0] || lines[1]) rects.push({slot: "hook", x: box.left, y: box.top, w: 720 - box.left - box.right, h: lines[1] ? 108 : 52});
    if (state.step >= 0) rects.push({slot: "number", x: box.left, y: 480 + box.top - 96, w: 360, h: 84});
    for (var s = 0; s < state.stickers.length && s < 2; s++) {
      rects.push({slot: "sticker", x: state.stickers[s].x || 480, y: state.stickers[s].y || 360, w: 120, h: 72});
    }
    if (state.chunk >= 0) rects.push({slot: "subtitle", x: box.left, y: 1280 - box.bottom - 96, w: 720 - box.left - box.right, h: 96});
    return rects;
  };
})();
