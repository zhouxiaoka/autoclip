import raf from "rc-util/es/raf";
import * as React from 'react';
function smoothScrollOffset(offset) {
  return Math.floor(Math.pow(offset, 0.5));
}
export function getPageXY(e, horizontal) {
  var obj = 'touches' in e ? e.touches[0] : e;
  return obj[horizontal ? 'pageX' : 'pageY'] - window[horizontal ? 'scrollX' : 'scrollY'];
}
export default function useScrollDrag(inVirtual, componentRef, onScrollOffset) {
  React.useEffect(function () {
    var ele = componentRef.current;
    if (inVirtual && ele) {
      var mouseDownLock = false;
      var rafId;
      var _offset;
      var stopScroll = function stopScroll() {
        raf.cancel(rafId);
      };
      var continueScroll = function continueScroll() {
        stopScroll();
        rafId = raf(function () {
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