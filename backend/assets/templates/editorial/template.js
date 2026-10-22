/* 杂志风叠加层。大标题停在下半，整段都在，不在 2.4 秒后收起，也不盖住脸。
   标题下是金线、当前这句中文（强调词更亮）和斜体英文原句，最底是署名。
   renderFrame(t) 只由 t 决定。until_frame 不再用来藏标题；关字幕时 fill 会把标题清掉。 */
(function () {
  var data = null;
  var SAFE = {
    xiaohongshu: {top: 96, bottom: 168, left: 48, right: 48},
    douyin: {top: 72, bottom: 220, left: 36, right: 36},
    tiktok: {top: 80, bottom: 210, left: 36, right: 36},
    instagram_reels: {top: 88, bottom: 200, left: 40, right: 40},
    youtube_shorts: {top: 72, bottom: 180, left: 36, right: 36}
  };
  // face_y 0.38 puts the face near y=486. The headline starts under that, on the chest.
  var HEAD_CLEAR = 700;

  function frameIndex(t) {
    return Math.max(0, Math.floor(t * data.fps + 1e-4));
  }

  function insets() {
    return data.safe || SAFE[data.safe_area] || SAFE.xiaohongshu;
  }

  function creditText() {
    var people = data.speakers || [];
    if (people.length && people[0].name) {
      return people[0].role ? people[0].name + "  " + people[0].role : String(people[0].name);
    }
    return data.kicker || "";
  }

  function stateAt(t) {
    var index = frameIndex(t);
    var hook = (data.hook && data.hook.text) || "";
    var word = -1;
    var emphasis = "";
    var source = "";
    var words = data.words || [];
    for (var i = 0; i < words.length; i++) {
      var item = words[i];
      if (index >= item.start_frame && index < item.end_frame) {
        word = i;
        emphasis = item.emphasis || "";
        source = item.original || "";
        break;
      }
    }
    var gloss = "";
    var cards = data.gloss || [];
    for (var g = 0; g < cards.length; g++) {
      var card = cards[g];
      if (index >= card.start_frame && index < card.end_frame) {
        gloss = card.id;
        break;
      }
    }
    var step = -1;
    var number = data.number;
    if (number && index >= number.start_frame && index < number.end_frame) {
      var span = Math.max(1, number.end_frame - number.start_frame);
      var steps = number.steps || 8;
      var delta = index - number.start_frame;
      step = 0;
      while (step + 1 < steps && (step + 1) * span <= delta * steps) step += 1;
    } else if (number && index >= number.end_frame && index < (number.hold_frame || number.end_frame)) {
      step = (number.steps || 8) - 1;
    }
    var credit = creditText();
    return {
      hash: [hook, String(word), emphasis, source, gloss, String(step), credit].join("|"),
      hook: hook,
      word: word,
      emphasis: emphasis,
      source: source,
      gloss: gloss,
      step: step,
      credit: credit
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

  function metrics(state) {
    var gap = 10;
    var glossH = state.gloss ? 72 : 0;
    var hookLines = state.hook ? Math.min(2, String(state.hook).split("\n").length) : 0;
    var hookH = hookLines ? hookLines * 64 : 0;
    var ruleH = state.hook ? 2 : 0;
    var subH = 0;
    var sourceH = 0;
    if (state.word >= 0) {
      var item = (data.words || [])[state.word] || {};
      subH = Math.min(2, String(item.text || "").split("\n").length || 1) * 44;
      if (item.original) sourceH = Math.min(2, String(item.original).split("\n").length) * 24;
    }
    var creditH = state.credit ? 22 : 0;
    var parts = [glossH, hookH, ruleH, subH, sourceH, creditH].filter(function (h) { return h > 0; });
    var total = 0;
    for (var i = 0; i < parts.length; i++) total += parts[i];
    if (parts.length > 1) total += (parts.length - 1) * gap;
    var box = insets();
    var top = 1280 - box.bottom - total;
    if (top < HEAD_CLEAR) top = HEAD_CLEAR;
    return {box: box, top: top, gap: gap, glossH: glossH, hookH: hookH, ruleH: ruleH, subH: subH, sourceH: sourceH, creditH: creditH};
  }

  function numberOrigin(state) {
    var laid = metrics(state);
    var h = 80;
    var y = laid.top - laid.gap - h;
    if (y < HEAD_CLEAR) y = HEAD_CLEAR;
    return {x: 720 - laid.box.right - 220, y: y, w: 220, h: h};
  }

  function paint(state) {
    var box = insets();
    var stack = document.getElementById("stack");
    stack.style.left = box.left + "px";
    stack.style.right = box.right + "px";
    stack.style.bottom = box.bottom + "px";
    document.getElementById("hook").textContent = state.hook || "";
    document.getElementById("rule").style.display = state.hook ? "block" : "none";
    document.getElementById("kicker").textContent = state.credit || "";
    var gloss = document.getElementById("gloss");
    gloss.innerHTML = "";
    if (state.gloss) {
      var cards = data.gloss || [];
      for (var i = 0; i < cards.length; i++) {
        if (cards[i].id === state.gloss) {
          gloss.innerHTML = "<b>" + escapeText(cards[i].title) + "</b>" + escapeText(cards[i].body || "");
          break;
        }
      }
    }
    var num = document.getElementById("num");
    var origin = numberOrigin(state);
    num.style.right = box.right + "px";
    num.style.top = origin.y + "px";
    num.style.bottom = "auto";
    if (state.step < 0 || !data.number) {
      num.innerHTML = "";
    } else {
      var shown = Math.round(data.number.value * (state.step + 1) / (data.number.steps || 8));
      num.innerHTML = escapeText(String(shown)) + "<small>" + escapeText(data.number.unit || "") + "</small>";
    }
    var sub = document.getElementById("sub");
    var source = document.getElementById("source");
    if (state.word < 0) {
      sub.innerHTML = "";
      source.innerHTML = "";
      return;
    }
    var item = (data.words || [])[state.word];
    sub.innerHTML = highlight(item.text, item.emphasis) + " ";
    source.innerHTML = item.original ? highlight(item.original, item.emphasis) : "";
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
    var laid = metrics(state);
    var box = laid.box;
    var rects = [];
    var y = laid.top;
    var width = 720 - box.left - box.right;
    function take(slot, h, w) {
      if (!h) return;
      rects.push({slot: slot, x: box.left, y: y, w: w || width, h: h});
      y += h + laid.gap;
    }
    take("gloss", laid.glossH, 420);
    take("hook", laid.hookH);
    if (laid.ruleH) y += laid.ruleH + laid.gap;
    take("subtitle", laid.subH);
    take("source", laid.sourceH);
    take("kicker", laid.creditH, 420);
    if (state.step >= 0) {
      var origin = numberOrigin(state);
      rects.push({slot: "number", x: origin.x, y: origin.y, w: origin.w, h: origin.h});
    }
    return rects;
  };
})();
