/* 杂志风，1080×1920。大标题只在封面上，成片不烧杂志标题。
   中文按短语做卡拉 OK：没说到 38%，说到变纸白并扫一条黄油下划线。
   一个时刻最多一个倾斜的衬线金句。英文按词从暗到黄油再到纸白。
   刊头（deck）和署名还在。renderFrame(t) 只由 t 决定。 */
(function () {
  var data = null;
  var seenMoment = null;

  function esc(value) {
    return String(value).replace(/[&<>]/g, function (ch) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;"}[ch];
    });
  }

  function lines() {
    // The magazine headline is the cover title. The clip does not burn it.
    return [];
  }

  function moments() {
    if (data.moments && data.moments.length) return data.moments;
    var words = data.words || [];
    var built = [];
    for (var i = 0; i < words.length; i++) {
      var word = words[i];
      var t0 = word.start_frame / data.fps;
      var t1 = word.end_frame / data.fps;
      var text = String(word.text || "").replace(/\n/g, "");
      built.push({
        t0: t0,
        t1: t1,
        speaker: word.speaker || "",
        zh: [{s: text, t0: t0, t1: t1, key: !!word.emphasis, acc: !!word.emphasis}],
        en: enFrom(String(word.original || ""), t0, t1)
      });
    }
    return built;
  }

  function enFrom(original, t0, t1) {
    var tokens = String(original || "").split(/\s+/).filter(Boolean);
    if (!tokens.length) return [];
    var weights = tokens.map(function (token) { return Math.max(token.length, 1); });
    var total = weights.reduce(function (sum, weight) { return sum + weight; }, 0);
    var span = Math.max(t1 - t0, 0.05);
    var cursor = t0;
    return tokens.map(function (token, index) {
      var dur = span * weights[index] / total;
      var row = {w: token, t0: cursor, t1: cursor + dur, key: false};
      cursor += dur;
      return row;
    });
  }

  function momentAt(t) {
    var list = moments();
    var found = null;
    for (var i = 0; i < list.length; i++) {
      if (t >= list[i].t0 && t < list[i].t1) found = list[i];
    }
    return found;
  }

  function lineWidth(node) {
    var display = node.style.display;
    node.style.display = "inline-block";
    var width = node.scrollWidth;
    node.style.display = display;
    var stroke = 0;
    if (window.getComputedStyle) {
      stroke = parseFloat(getComputedStyle(node).webkitTextStrokeWidth) || 0;
    }
    return width + stroke;
  }

  function faceReady(node, face) {
    if (!face || !document.fonts || !document.fonts.check) return true;
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
    while (lineWidth(box) > limit && text.replace(/…$/, "").length > 1 && guard < 120) {
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

  function stateName(t, row) {
    if (t >= row.t1) return " past";
    if (t >= row.t0) return " now";
    return "";
  }

  function framesSince(t, t0) {
    return Math.floor((t - t0) * (data.fps || 30) + 1e-4);
  }

  function sweepAt(t, phrase) {
    return Math.min(100, 25 * (framesSince(t, phrase.t0) + 1));
  }

  // A slight pop as a new screen lands, settled by the fourth frame.
  var POP = [1.04, 1.025, 1.01];

  function popAt(moment, t) {
    var k = framesSince(t, moment.t0);
    return k >= 0 && k < POP.length ? POP[k] : 1;
  }

  function zhHtml(moment, t) {
    var html = "";
    var list = moment.zh || [];
    for (var i = 0; i < list.length; i++) {
      var phrase = list[i];
      var state = stateName(t, phrase);
      // The preview sweeps the underline in over about 4 frames. Quarter steps keep the
      // capture to 3 extra frames per phrase; the hold shows the full bar.
      var sweep = state === " now" ? sweepAt(t, phrase) : 0;
      var text = String(phrase.s || "");
      var mark = phrase.acc ? String(phrase.hl || "") : "";
      var at = mark ? text.indexOf(mark) : -1;
      // Gold serif on a shorter emphasis only: 「AI其实是一块」 stays sans, 「五层蛋糕」 turns gold.
      // The whole caption in that face is a cover-style title (「走过弯路」), so it stays a caption.
      var partial = at >= 0 && mark.length < text.length;
      if (partial) {
        var open = '<span class="p' + state + '" style="--u:' + sweep + '%">';
        if (at > 0) html += open + esc(text.slice(0, at)) + "</span>";
        html += '<span class="p acc' + state + '" style="--u:' + sweep + '%">' + esc(mark) + "</span>";
        if (at + mark.length < text.length) html += open + esc(text.slice(at + mark.length)) + "</span>";
        continue;
      }
      html += '<span class="p' + state + '" style="--u:' + sweep + '%">' + esc(text) + "</span>";
    }
    return html;
  }

  function enHtml(moment, t) {
    var html = "";
    var list = moment.en || [];
    for (var i = 0; i < list.length; i++) {
      var word = list[i];
      html += (i ? " " : "") + '<span class="w' + stateName(t, word) + '">' + esc(word.w) + "</span>";
    }
    return html;
  }

  function folioText() {
    var left = String(data.issue || "");
    if (data.src_start_tc) left = left ? left + " · 原片 " + data.src_start_tc : "原片 " + data.src_start_tc;
    return left;
  }

  function paintStatic() {
    var hookLines = lines();
    var html = "";
    for (var i = 0; i < hookLines.length && i < 2; i++) {
      html += '<span class="ln' + (hookLines[i][1] ? " acc" : "") + '">' + esc(hookLines[i][0]) + "</span>";
    }
    var block = document.getElementById("h-l");
    block.innerHTML = html;
    fitHook();
    document.getElementById("kick").textContent = data.deck || "";
    document.getElementById("trk").textContent = data.hook_trk || data.credit || "";
    document.getElementById("f-l").textContent = folioText();
  }

  window.setData = function (fill) {
    data = fill || {};
    seenMoment = null;
    paintStatic();
  };

  function fitHook() {
    var nodes = (document.getElementById("h-l").children) || [];
    for (var n = 0; n < nodes.length; n++) fit(nodes[n], 96, 60, 4, 960, '900 96px "Noto Serif SC"');
  }

  window.renderFrame = function (t) {
    fitHook();
    var moment = momentAt(t);
    var zh = document.getElementById("zh");
    var en = document.getElementById("en");
    var pop = 1;
    if (moment) {
      var mark = moment.t0 + ":" + (moment.zh || []).map(function (phrase) { return phrase.s; }).join("/");
      if (seenMoment !== mark) {
        seenMoment = mark;
        zh.style.fontSize = "";
        en.style.fontSize = "";
      }
      zh.innerHTML = zhHtml(moment, t);
      en.innerHTML = enHtml(moment, t);
      fit(zh, 52, 40, 2, 960, '500 52px "Noto Sans CJK SC"');
      pop = popAt(moment, t);
      fit(en, 36, 24, 2, 960, 'italic 36px "Instrument Serif"');
    } else {
      zh.innerHTML = "";
      en.innerHTML = "";
      seenMoment = null;
      pop = 1;
    }
    var gloss = document.getElementById("gloss");
    var index = Math.max(0, Math.floor(t * data.fps + 1e-4));
    var card = "";
    var cards = data.gloss || [];
    for (var i = 0; i < cards.length; i++) {
      if (index >= cards[i].start_frame && index < cards[i].end_frame) {
        card = cards[i].title || "";
        break;
      }
    }
    gloss.textContent = card;
    var number = data.number;
    var step = -1;
    if (number && index >= number.start_frame && index < number.end_frame) {
      var span = Math.max(1, number.end_frame - number.start_frame);
      var steps = number.steps || 8;
      var delta = index - number.start_frame;
      step = 0;
      while (step + 1 < steps && (step + 1) * span <= delta * steps) step += 1;
    } else if (number && index >= number.end_frame && index < (number.hold_frame || number.end_frame)) {
      step = (number.steps || 8) - 1;
    }
    document.getElementById("num").textContent = step < 0 || !number ? "" : String(Math.round(number.value * (step + 1) / (number.steps || 8))) + (number.unit || "");
    zh.style.transformOrigin = "0 60%";
    zh.style.transform = pop === 1 ? "" : "scale(" + pop + ")";
    var headline = lines().map(function (line) { return line[0]; }).join("\n");
    return [headline, zh.innerHTML, en.innerHTML, card, String(step), pop.toFixed(3)].join("|");
  };

  window.occupiedRects = function (t) {
    var rects = [];
    var hookLines = lines();
    if (hookLines.length) rects.push({slot: "hook", x: 60, y: 1192, w: 960, h: 209});
    if (data.deck) rects.push({slot: "kicker", x: 60, y: 1115, w: 960, h: 44});
    if (data.hook_trk || data.credit) rects.push({slot: "credit", x: 60, y: 1443, w: 960, h: 22});
    var moment = momentAt(t);
    if (moment) {
      rects.push({slot: "subtitle", x: 60, y: 1565, w: 960, h: 61});
      if (moment.en && moment.en.length) rects.push({slot: "source", x: 60, y: 1653, w: 960, h: 34});
    }
    if (folioText()) rects.push({slot: "folio", x: 60, y: 1840, w: 960, h: 17});
    var index = Math.max(0, Math.floor(t * (data.fps || 30) + 1e-4));
    var cards = data.gloss || [];
    for (var i = 0; i < cards.length; i++) {
      if (index >= cards[i].start_frame && index < cards[i].end_frame) {
        rects.push({slot: "gloss", x: 60, y: 980, w: 420, h: 72});
        break;
      }
    }
    return rects;
  };
})();
