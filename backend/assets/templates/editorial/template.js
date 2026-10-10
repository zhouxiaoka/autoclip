/* 杂志风叠加层。renderFrame(t) 只由 t 决定，哈希在钩子、词、强调、术语卡、数字档位变化时改变。 */
(function () {
  var data = null;

  function frameIndex(t) {
    return Math.max(0, Math.floor(t * data.fps + 1e-4));
  }

  function stateAt(t) {
    var index = frameIndex(t);
    var hook = data.hook && index < data.hook.until_frame ? (data.hook.text || "") : "";
    var word = -1;
    var emphasis = "";
    var words = data.words || [];
    for (var i = 0; i < words.length; i++) {
      var item = words[i];
      if (index >= item.start_frame && index < item.end_frame) {
        word = i;
        emphasis = item.emphasis || "";
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
    return {
      hash: [hook, String(word), emphasis, gloss, String(step), data.kicker || ""].join("|"),
      hook: hook,
      word: word,
      emphasis: emphasis,
      gloss: gloss,
      step: step
    };
  }

  function escapeText(value) {
    return String(value).replace(/[&<>]/g, function (ch) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;"}[ch];
    });
  }

  function paint(state) {
    document.getElementById("kicker").innerHTML = "<i></i>" + escapeText(data.kicker || "");
    document.getElementById("hook").textContent = state.hook || "";
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
    if (state.step < 0 || !data.number) {
      num.innerHTML = "";
    } else {
      var shown = Math.round(data.number.value * (state.step + 1) / (data.number.steps || 8));
      num.innerHTML = escapeText(String(shown)) + "<small>" + escapeText(data.number.unit || "") + "</small>";
    }
    var sub = document.getElementById("sub");
    if (state.word < 0) {
      sub.innerHTML = "";
      return;
    }
    var group = Math.floor(state.word / 8) * 8;
    var words = data.words || [];
    var html = "";
    for (var w = group; w < Math.min(words.length, group + 8); w++) {
      var text = escapeText(words[w].text);
      if (w === state.word && words[w].emphasis) html += "<em>" + text + "</em> ";
      else if (w === state.word) html += "<strong>" + text + "</strong> ";
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
    var rects = [];
    if (data.kicker) rects.push({slot: "kicker", x: 48, y: 72, w: 280, h: 28});
    if (state.hook) rects.push({slot: "hook", x: 48, y: 108, w: 624, h: 150});
    if (state.gloss) rects.push({slot: "gloss", x: 48, y: 860, w: 420, h: 96});
    if (state.step >= 0) rects.push({slot: "number", x: 400, y: 420, w: 272, h: 120});
    if (state.word >= 0) rects.push({slot: "subtitle", x: 48, y: 1040, w: 624, h: 88});
    return rects;
  };
})();
