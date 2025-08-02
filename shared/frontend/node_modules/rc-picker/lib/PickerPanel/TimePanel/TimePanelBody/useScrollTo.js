"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = useScrollTo;
var _rcUtil = require("rc-util");
var _raf = _interopRequireDefault(require("rc-util/lib/raf"));
var _isVisible = _interopRequireDefault(require("rc-util/lib/Dom/isVisible"));
var React = _interopRequireWildcard(require("react"));
var SPEED_PTG = 1 / 3;
function useScrollTo(ulRef, value) {
  // ========================= Scroll =========================
  var scrollingRef = React.useRef(false);
  var scrollRafRef = React.useRef(null);
  var scrollDistRef = React.useRef(null);
  var isScrolling = function isScrolling() {
    return scrollingRef.current;
  };
  var stopScroll = function stopScroll() {
    _raf.default.cancel(scrollRafRef.current);
    scrollingRef.current = false;
  };
  var scrollRafTimesRef = React.useRef();
  var startScroll = function startScroll() {
    var ul = ulRef.current;
    scrollDistRef.current = null;
    scrollRafTimesRef.current = 0;
    if (ul) {
      var targetLi = ul.querySelector("[data-value=\"".concat(value, "\"]"));
      var firstLi = ul.querySelector("li");
      var doScroll = function doScroll() {
        stopScroll();
        scrollingRef.current = true;
        scrollRafTimesRef.current += 1;
        var currentTop = ul.scrollTop;
        var firstLiTop = firstLi.offsetTop;
        var targetLiTop = targetLi.offsetTop;
        var targetTop = targetLiTop - firstLiTop;

        // Wait for element exist. 5 frames is enough
        if (targetLiTop === 0 && targetLi !== firstLi || !(0, _isVisible.default)(ul)) {
          if (scrollRafTimesRef.current <= 5) {
            scrollRafRef.current = (0, _raf.default)(doScroll);
          }
          return;
        }
        var nextTop = currentTop + (targetTop - currentTop) * SPEED_PTG;
        var dist = Math.abs(targetTop - nextTop);

        // Break if dist get larger, which means user is scrolling
        if (scrollDistRef.current !== null && scrollDistRef.current < dist) {
          stopScroll();
          return;
        }
        scrollDistRef.current = dist;

        // Stop when dist is less than 1
        if (dist <= 1) {
          ul.scrollTop = targetTop;
          stopScroll();
          return;
        }

        // IE not support `scrollTo`
        ul.scrollTop = nextTop;
        scrollRafRef.current = (0, _raf.default)(doScroll);
      };
      if (targetLi && firstLi) {
        doScroll();
      }
    }
  };

  // ======================== Trigger =========================
  var syncScroll = (0, _rcUtil.useEvent)(startScroll);
  return [syncScroll, stopScroll, isScrolling];
}