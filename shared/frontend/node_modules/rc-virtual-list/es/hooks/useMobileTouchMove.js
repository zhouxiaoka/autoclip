import useLayoutEffect from "rc-util/es/hooks/useLayoutEffect";
import { useRef } from 'react';
var SMOOTH_PTG = 14 / 15;
export default function useMobileTouchMove(inVirtual, listRef, callback) {
  var touchedRef = useRef(false);
  var touchXRef = useRef(0);
  var touchYRef = useRef(0);
  var elementRef = useRef(null);

  // Smooth scroll
  var intervalRef = useRef(null);

  /* eslint-disable prefer-const */
  var cleanUpEvents;
  var onTouchMove = function onTouchMove(e) {
    if (touchedRef.current) {
      var currentX = Math.ceil(e.touches[0].pageX);
      var currentY = Math.ceil(e.touches[0].pageY);
      var offsetX = touchXRef.current - currentX;
      var offsetY = touchYRef.current - currentY;
      var _isHorizontal = Math.abs(offsetX) > Math.abs(offsetY);
      if (_isHorizontal) {
        touchXRef.current = currentX;
      } else {
        touchYRef.current = currentY;
      }
      var scrollHandled = callback(_isHorizontal, _isHorizontal ? offsetX : offsetY, false, e);
      if (scrollHandled) {
        e.preventDefault();
      }

      // Smooth interval
      clearInterval(intervalRef.current);
      if (scrollHandled) {
        intervalRef.current = setInterval(function () {
          if (_isHorizontal) {
            offsetX *= SMOOTH_PTG;
          } else {
            offsetY *= SMOOTH_PTG;
          }
          var offset = Math.floor(_isHorizontal ? offsetX : offsetY);
          if (!callback(_isHorizontal, offset, true) || Math.abs(offset) <= 0.1) {
            clearInterval(intervalRef.current);
          }
        }, 16);
      }
    }
  };
  var onTouchEnd = function onTouchEnd() {
    touchedRef.current = false;
    cleanUpEvents();
  };
  var onTouchStart = function onTouchStart(e) {
    cleanUpEvents();
    if (e.touches.length === 1 && !touchedRef.current) {
      touchedRef.current = true;
      touchXRef.current = Math.ceil(e.touches[0].pageX);
      touchYRef.current = Math.ceil(e.touches[0].pageY);
      elementRef.current = e.target;
      elementRef.current.addEventListener('touchmove', onTouchMove, {
        passive: false
      });
      elementRef.current.addEventListener('touchend', onTouchEnd, {
        passive: true
      });
    }
  };
  cleanUpEvents = function cleanUpEvents() {
    if (elementRef.current) {
      elementRef.current.removeEventListener('touchmove', onTouchMove);
      elementRef.current.removeEventListener('touchend', onTouchEnd);
    }
  };
  useLayoutEffect(function () {
    if (inVirtual) {
      listRef.current.addEventListener('touchstart', onTouchStart, {
        passive: true
      });
    }
    return function () {
      var _listRef$current;
      (_listRef$current = listRef.current) === null || _listRef$current === void 0 || _listRef$current.removeEventListener('touchstart', onTouchStart);
      cleanUpEvents();
      clearInterval(intervalRef.current);
    };
  }, [inVirtual]);
}