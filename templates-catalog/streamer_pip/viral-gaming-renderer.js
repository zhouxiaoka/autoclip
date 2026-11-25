/* Viral Gaming Clip transparent SVG overlay renderer (1080x1920 @ 30fps).
   Full-bleed short-form gaming layouts (90%+ video area, zero poster banners):
     - viral_split: 38% top facecam + 62% bottom gameplay, seam kinetic captions, impact slam banner
     - viral_pip:   100% full-bleed gameplay + 360x360 rounded floating reaction cam + lower-third captions
     - viral_full:  automatic fallback when no camera is active (full-screen gameplay or pure facecam)
   Supports English word-by-word kinetic highlighting and Chinese punch-word highlighting.
   100% deterministic from (fill, tSeconds) with zero external URLs. */
(function (global) {
  'use strict';

  var mctx = document.createElement('canvas').getContext('2d');

  function esc(v) {
    return String(v || '').replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[c];
    });
  }

  function fitSize(text, startPx, maxW, fontSpec) {
    mctx.font = fontSpec.replace('{sz}', startPx);
    var w = Math.max(1, mctx.measureText(text).width);
    return Math.min(startPx, Math.floor((startPx * maxW) / w));
  }

  function activeEvent(cp, frameIndex) {
    var list = (cp && cp.events) || [];
    for (var i = 0; i < list.length; i++) {
      var ev = list[i];
      var d = frameIndex - ev.frame;
      var total = ev.enter + ev.hold + ev.exit;
      if (d >= 0 && d < total) {
        var phase = Math.max(0, Math.min(1, (d + 1) / Math.max(1, ev.enter), (total - d) / Math.max(1, ev.exit)));
        return { ev: ev, phase: phase };
      }
    }
    return null;
  }

  function isEnglishText(s) {
    return /^[\x20-\x7e\u2014\u2018\u2019\u201c\u201d\u2026]+$/.test(String(s || '').trim());
  }

  function renderCaption(moment, tSeconds, y, accent, maxW, startPx, fontEn, lang) {
    if (!moment || !moment.zh || !moment.zh.length) return { svg: '', digest: '' };
    var parts = [];
    for (var i = 0; i < moment.zh.length; i++) {
      if (moment.zh[i] && moment.zh[i].s) parts.push(moment.zh[i].s);
    }
    var rawText = parts.join(lang === 'en' ? ' ' : '').trim();
    if (!rawText) return { svg: '', digest: '' };

    var useEn = lang === 'en' || isEnglishText(rawText);
    if (useEn) {
      var words = rawText.toUpperCase().split(/\s+/).filter(Boolean);
      if (!words.length) return { svg: '', digest: '' };
      var mStart = Number(moment.start || 0);
      var mEnd = Number(moment.end || (mStart + 1.5));
      var frac = Math.max(0, Math.min(0.999, (tSeconds - mStart) / Math.max(0.08, mEnd - mStart)));
      var activeIdx = Math.floor(frac * words.length);
      var full = words.join(' ');
      var sz = fitSize(full, startPx, maxW, '900 {sz}px ' + fontEn);
      var tspans = '';
      for (var w = 0; w < words.length; w++) {
        tspans += '<tspan fill="' + (w === activeIdx ? accent : '#FFFFFF') + '">' + esc(words[w]) + (w < words.length - 1 ? ' ' : '') + '</tspan>';
      }
      var strokeW = Math.max(10, Math.round(sz * 0.22));
      return {
        svg: '<text x="540" y="' + y + '" text-anchor="middle" font-size="' + sz + '" font-family="' + fontEn + '" stroke="#08080C" stroke-width="' + strokeW + '" stroke-linejoin="round" paint-order="stroke">' + tspans + '</text>',
        digest: full + '@' + activeIdx,
      };
    }

    // Chinese / CJK heavy bold caption with automatic punch-word & number highlighting
    var szZh = fitSize(rawText, Math.round(startPx * 0.86), maxW, '900 {sz}px "PingFang SC", "Noto Sans CJK SC", sans-serif');
    var hl = esc(rawText).replace(
      /(\d+\s*[个小秒米万亿倍%]+|GTA\s*\d*|MVP|BOSS|ACE|KO|绝杀|翻车|卧槽|离谱|直接|炸了|完了|不可能)/gi,
      '<tspan fill="' + accent + '">$1</tspan>'
    );
    var strokeZh = Math.max(10, Math.round(szZh * 0.22));
    return {
      svg: '<text x="540" y="' + y + '" text-anchor="middle" font-size="' + szZh + '" font-weight="900" font-family="PackSans" fill="#FFFFFF" stroke="#08080C" stroke-width="' + strokeZh + '" stroke-linejoin="round" paint-order="stroke">' + hl + '</text>',
      digest: rawText,
    };
  }

  function mount(defaults) {
    var state = {};
    var root = document.getElementById('stage');

    window.setData = function (fill) {
      state = fill || {};
    };

    window.renderFrame = function (tSeconds) {
      var t = Number(tSeconds) || 0;
      var fps = state.fps || 30;
      var frameIndex = Math.floor(t * fps + 1e-4);
      var cp = state.creator_pack || {};
      var layoutId = cp.layout_id || defaults.layout || 'viral_split';
      var cam = Boolean(cp.camera_active && cp.slots && cp.slots.camera);
      var effectiveMode = (!cam && layoutId === 'viral_split') ? 'viral_full' : layoutId;
      var accent = defaults.accent || (cp.theme && cp.theme.accent) || '#FFE14D';
      var impactColor = defaults.impactColor || '#FF5145';
      var fontEn = defaults.slantCaptions ? 'PackSlant' : 'PackBlack';
      var lang = state.audience_language || 'en';

      var hookText = (state.title_lines || []).join(' ').trim();
      var host = (cp.host || (state.guest && state.guest.name) || 'LIVE').toUpperCase();
      var moment = global.ACTemplate ? global.ACTemplate.momentAt(state, t) : null;

      // Auto-dismissing opening hook (visible 0..2.3s, fades out 2.3..2.9s)
      var hookAlpha = t < 2.3 ? 1 : (t < 2.9 ? Math.max(0, 1 - (t - 2.3) / 0.6) : 0);
      var hookStep = hookAlpha > 0 ? hookAlpha.toFixed(2) : '0';

      var act = activeEvent(cp, frameIndex);
      var evPhase = act ? act.phase : 0;
      var evLabel = (act && act.ev.label) ? act.ev.label : (defaults.defaultEventLabel || 'WASTED');
      var evDigest = act ? (act.ev.id + ':' + evPhase.toFixed(2)) : 'none';

      var svg = '';
      var capOut = { svg: '', digest: '' };

      if (effectiveMode === 'viral_split') {
        // 38% top facecam (0..730) + 62% bottom gameplay (730..1920)
        svg += '<defs>'
          + '<linearGradient id="seamTop" x2="0" y2="1"><stop offset="0%" stop-color="#000" stop-opacity="0"/><stop offset="100%" stop-color="#000" stop-opacity="0.58"/></linearGradient>'
          + '<linearGradient id="seamBot" x2="0" y2="1"><stop offset="0%" stop-color="#000" stop-opacity="0.58"/><stop offset="100%" stop-color="#000" stop-opacity="0"/></linearGradient>'
          + '<linearGradient id="seamLine" x1="0" x2="1" y1="0" y2="0"><stop offset="0%" stop-color="' + impactColor + '"/><stop offset="50%" stop-color="' + accent + '"/><stop offset="100%" stop-color="' + impactColor + '"/></linearGradient>'
          + '</defs>';
        svg += '<rect x="0" y="640" width="1080" height="90" fill="url(#seamTop)"/>';
        svg += '<rect x="0" y="730" width="1080" height="100" fill="url(#seamBot)"/>';
        svg += '<rect x="0" y="727" width="1080" height="5" fill="url(#seamLine)" opacity="0.88"/>';

        // Minimal LIVE / streamer badge top-left
        var badgeW = Math.min(280, Math.max(132, 74 + host.length * 14));
        svg += '<g opacity="0.90">'
          + '<rect x="40" y="102" width="' + badgeW + '" height="44" rx="8" fill="#101016" fill-opacity="0.72"/>'
          + '<circle cx="66" cy="124" r="6" fill="#FF4B4B"/>'
          + '<text x="84" y="134" font-size="25" font-family="PackBlack" letter-spacing="1.5" fill="#FFFFFF">' + esc(host) + '</text>'
          + '</g>';

        // Opening hook pill (0..2.9s only)
        if (hookAlpha > 0.01 && hookText) {
          var hFont = isEnglishText(hookText) ? 'PackSlant' : 'PackSans';
          var hsz = fitSize(hookText, isEnglishText(hookText) ? 50 : 46, 740, '900 {sz}px ' + hFont);
          svg += '<g opacity="' + hookStep + '">'
            + '<rect x="130" y="622" width="820" height="80" rx="40" fill="#0F0F15" fill-opacity="0.90" stroke="' + accent + '" stroke-width="3.5"/>'
            + '<text x="540" y="' + (662 + Math.round(hsz * 0.34)) + '" text-anchor="middle" font-size="' + hsz + '" font-weight="900" font-family="' + hFont + '" letter-spacing="1.5" fill="#FFFFFF">' + esc(hookText.toUpperCase()) + '</text>'
            + '</g>';
        }

        // Impact-only slam banner across game zone (invisible during normal play)
        if (evPhase > 0.01) {
          var sc = 0.88 + 0.12 * evPhase;
          svg += '<g opacity="' + evPhase.toFixed(3) + '" transform="translate(540 1200) scale(' + sc.toFixed(3) + ')">'
            + '<rect x="-540" y="-88" width="1080" height="176" fill="#0A0A0E" fill-opacity="0.80"/>'
            + '<rect x="-540" y="-88" width="1080" height="6" fill="' + impactColor + '"/>'
            + '<rect x="-540" y="82" width="1080" height="6" fill="' + impactColor + '"/>'
            + '<text x="0" y="46" text-anchor="middle" font-size="144" font-family="PackSlant" letter-spacing="6" fill="' + impactColor + '" stroke="#000000" stroke-width="10" paint-order="stroke">' + esc(evLabel) + '</text>'
            + '</g>';
        }

        var capY = hookAlpha > 0.25 ? 794 : 760;
        capOut = renderCaption(moment, t, capY, accent, 960, 88, fontEn, lang);
        svg += capOut.svg;
      } else if (effectiveMode === 'viral_pip') {
        // 100% full-bleed gameplay + glowing border on 360x360 rounded top-right PiP camera
        svg += '<defs>'
          + '<linearGradient id="botScrim" x2="0" y2="1"><stop offset="0%" stop-color="#000" stop-opacity="0"/><stop offset="100%" stop-color="#000" stop-opacity="0.78"/></linearGradient>'
          + '</defs>';
        svg += '<rect x="0" y="1220" width="1080" height="700" fill="url(#botScrim)"/>';
        if (cam && cp.slots && cp.slots.camera) {
          var cr = cp.slots.camera;
          svg += '<rect x="' + cr[0] + '" y="' + cr[1] + '" width="' + cr[2] + '" height="' + cr[3] + '" rx="28" fill="none" stroke="' + accent + '" stroke-width="6"/>';
        }
        if (hookAlpha > 0.01 && hookText) {
          var pFont = isEnglishText(hookText) ? 'PackBlack' : 'PackSans';
          var psz = fitSize(hookText, 38, 540, '900 {sz}px ' + pFont);
          svg += '<g opacity="' + hookStep + '">'
            + '<rect x="44" y="136" width="590" height="68" rx="14" fill="#14111D" fill-opacity="0.88" stroke="' + accent + '" stroke-width="2.5"/>'
            + '<text x="339" y="' + (170 + Math.round(psz * 0.34)) + '" text-anchor="middle" font-size="' + psz + '" font-weight="900" font-family="' + pFont + '" letter-spacing="1.2" fill="#FFF8EA">' + esc(hookText.toUpperCase()) + '</text>'
            + '</g>';
        }
        capOut = renderCaption(moment, t, 1420, accent, 960, 90, fontEn, lang);
        svg += capOut.svg;
      } else {
        // viral_full: 100% full-bleed gameplay or full-screen facecam
        svg += '<defs>'
          + '<linearGradient id="topScrim" x2="0" y2="1"><stop offset="0%" stop-color="#000" stop-opacity="0.55"/><stop offset="100%" stop-color="#000" stop-opacity="0"/></linearGradient>'
          + '<linearGradient id="botScrim" x2="0" y2="1"><stop offset="0%" stop-color="#000" stop-opacity="0"/><stop offset="100%" stop-color="#000" stop-opacity="0.78"/></linearGradient>'
          + '</defs>';
        svg += '<rect x="0" y="0" width="1080" height="340" fill="url(#topScrim)"/>';
        svg += '<rect x="0" y="1220" width="1080" height="700" fill="url(#botScrim)"/>';
        if (hookAlpha > 0.01 && hookText) {
          var fFont = isEnglishText(hookText) ? 'PackBlack' : 'PackSans';
          var fsz = fitSize(hookText, 52, 760, '900 {sz}px ' + fFont);
          svg += '<g opacity="' + hookStep + '">'
            + '<rect x="120" y="196" width="840" height="84" rx="42" fill="#111118" fill-opacity="0.88" stroke="' + accent + '" stroke-width="3.5"/>'
            + '<text x="540" y="' + (238 + Math.round(fsz * 0.34)) + '" text-anchor="middle" font-size="' + fsz + '" font-weight="900" font-family="' + fFont + '" letter-spacing="1.5" fill="#FFFFFF">' + esc(hookText.toUpperCase()) + '</text>'
            + '</g>';
        }
        if (evPhase > 0.01) {
          var fsc = 0.88 + 0.12 * evPhase;
          svg += '<g opacity="' + evPhase.toFixed(3) + '" transform="translate(540 1020) scale(' + fsc.toFixed(3) + ')">'
            + '<rect x="-540" y="-88" width="1080" height="176" fill="#0A0A0E" fill-opacity="0.80"/>'
            + '<rect x="-540" y="-88" width="1080" height="6" fill="' + impactColor + '"/>'
            + '<rect x="-540" y="82" width="1080" height="6" fill="' + impactColor + '"/>'
            + '<text x="0" y="46" text-anchor="middle" font-size="144" font-family="PackSlant" letter-spacing="6" fill="' + impactColor + '" stroke="#000000" stroke-width="10" paint-order="stroke">' + esc(evLabel) + '</text>'
            + '</g>';
        }
        capOut = renderCaption(moment, t, 1440, accent, 940, 88, fontEn, lang);
        svg += capOut.svg;
      }

      root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' + svg + '</svg>';
      return [effectiveMode, hookStep, capOut.digest, evDigest, cam ? '1' : '0'].join('|');
    };

    window.occupiedRects = function () {
      return [
        { slot: 'caption', x: 60, y: 700, w: 960, h: 140 },
      ];
    };

    return {
      setData: window.setData,
      renderFrame: window.renderFrame,
      occupiedRects: window.occupiedRects,
    };
  }

  global.ViralGamingPack = { mount: mount };
})(window);
