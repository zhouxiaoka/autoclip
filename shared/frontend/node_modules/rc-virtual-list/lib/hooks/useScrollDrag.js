"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = useScrollDrag;
exports.getPageXY = getPageXY;
var _raf = _interopRequireDefault(require("rc-util/lib/raf"));
var React = _interopRequireWildcard(require("react"));
function smoothScrollOffset(offset) {
  return Math.floor(Math.pow(offset, 0.5));
}
function getPageXY(e, horizontal) {
  var obj = 'touches' in e ? e.touches[0] : e;
  return obj[horizontal ? 'pageX' : 'pageY'] - window[horizontal ? 'scrollX' : 'scrollY'];
}
function useScrollDrag(inVirtual, componentRef, onScrollOffset) {
  React.useEffect(function () {
    var ele = componentRef.current;
    if (inVirtual && ele) {
      var mouseDownLock = false;
      var rafId;
      var _offset;
      var stopScroll = function stopScroll() {
        _raf.default.cancel(rafId);
      };
      var continueScroll = function continueScroll() {
        stopScroll();
        rafId = (0, _raf.default)(function () {
          onScrollOffset(_offset);
          continueScroll();
        });
      };
      var onMouseDown = function onMouseDown(e) {
        // Skip if element set draggable
        if (e.target.draggable || e.button !== 0) {
          return;
        }
        // Skip if nest List has handled this event
        var event = e;
        if (!event._virtualHandled) {
          event._virtualHandled = true;
          mouseDownLock = true;
        }
      };
      var onMouseUp = function onMouseUp() {
        mouseDownLock = false;
        stopScroll();
      };
      var onMouseMove = function onMouseMove(e) {
        if (mouseDownLock) {
          var mouseY = getPageXY(e, false);
          var _ele$getBoundingClien = ele.getBoundingClientRect(),
            top = _ele$getBoundingClien.top,
            bottom = _ele$getBoundingClien.bottom;
          if (mouseY <= top) {
            var diff = top - mouseY;
            _offset = -smoothScrollOffset(diff);
            continueScroll();
          } else if (mouseY >= bottom) {
            var _diff = mouseY - bottom;
            _offset = smoothScrollOffset(_diff);
            continueScroll();
          } else {
            stopScroll();
          }
        }
      };
      ele.addEventListener('mousedown', onMouseDown);
      ele.ownerDocument.addEventListener('mouseup', onMouseUp);
      ele.ownerDocument.addEventListener('mousemove', onMouseMove);
      return function () {
        ele.removeEventListener('mousedown', onMouseDown);
        ele.ownerDocument.removeEventListener('mouseup', onMouseUp);
        ele.ownerDocument.removeEventListener('mousemove', onMouseMove);
        stopScroll();
      };
    }
  }, [inVirtual]);
}