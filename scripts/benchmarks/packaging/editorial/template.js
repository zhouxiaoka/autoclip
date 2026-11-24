/* M0 测速夹具，不是要上线的杂志风模板。
   renderFrame(t) 是纯函数：画面只由 t 决定，哈希只在词、钩子、脚注、数字档位变化时改变。
   与 scripts/packaging_frame_benchmark.py 的 state_at 用同一套帧序号规则。 */
(function () {
  var data = null;

  function frameIndex(t) {
    return Math.floor(t * data.fps + 1e-4);
  }

  function stateAt(t) {
    var index = frameIndex(t);
    var hook = index < data.hook.until_frame ? data.hook.text : "";
    var word = -1;
    var emphasis = "";
    for (var i = 0; i < data.words.length; i++) {
      var item = data.words[i];
      if (index >= item.start_frame && index < item.end_frame) {
        word = i;
        emphasis = item.emphasis || "";
        break;
      }
    }
    var gloss = "";
    for (var g = 0; g < data.gloss.length; g++) {
      var card = data.gloss[g];
      if (index >= card.start_frame && index < card.end_frame) {
        gloss = card.id;
        break;
      }
    }
    var step = -1;
    var number = data.number;
    if (number && index >= number.start_frame && index < number.end_frame) {
      var span = number.end_frame - number.start_frame;
      var delta = index - number.start_frame;
      step = 0;
      while (step + 1 < number.steps && (step + 1) * span <= delta * number.steps) step += 1;
    } else if (number && index >= number.end_frame && index < number.hold_frame) {
      step = number.steps - 1;
    }
    return {
      hash: [hook, String(word), emphasis, gloss, String(step)].join("|"),
      word: word,
      emphasis: emphasis,
      gloss: gloss,
      hook: hook,
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
      for (var i = 0; i < data.gloss.length; i++) {
        if (data.gloss[i].id === state.gloss) {
          gloss.innerHTML = "<b>" + escapeText(data.gloss[i].title) + "</b>" + escapeText(data.gloss[i].body);
          break;
        }
      }
    }
    var num = document.getElementById("num");
    if (state.step < 0) {
      num.innerHTML = "";
    } else {
      var shown = Math.round(data.number.value * (state.step + 1) / data.number.steps);
      num.innerHTML = escapeText(String(shown)) + "<small>" + escapeText(data.number.unit || "") + "</small>";
    }
    var sub = document.getElementById("sub");
    if (state.word < 0) {
      sub.innerHTML = "";
      return;
    }
    var group = Math.floor(state.word / 8) * 8;
    var html = "";
    for (var w = group; w < Math.min(data.words.length, group + 8); w++) {
      var text = escapeText(data.words[w].text);
      if (w === state.word && data.words[w].emphasis) html += "<em>" + text + "</em>";
      else if (w === state.word) html += "<strong>" + text + "</strong>";
      else html += text;
    }
    sub.innerHTML = html;
  }

  window.setData = function (fill) {
    data = fill;
    window.__fill = fill;
  };

  window.renderFrame = function (t) {
    var state = stateAt(t);
    paint(state);
    return state.hash;
  };

  window.occupiedRects = function (t) {
    var state = stateAt(t);
    var width = window.innerWidth || 720;
    var height = window.innerHeight || 1280;
    var rects = [];
    if (state.hook) rects.push({x: width * 0.08, y: height * 0.09, w: width * 0.82, h: height * 0.16});
    if (state.gloss) rects.push({x: width * 0.08, y: height * 0.56, w: width * 0.42, h: height * 0.12});
    if (state.step >= 0) rects.push({x: width * 0.55, y: height * 0.34, w: width * 0.37, h: height * 0.14});
    if (state.word >= 0) rects.push({x: width * 0.08, y: height * 0.78, w: width * 0.84, h: height * 0.12});
    return rects;
  };
})();
