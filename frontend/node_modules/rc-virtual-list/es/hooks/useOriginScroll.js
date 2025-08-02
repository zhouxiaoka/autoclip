import { useRef } from 'react';
export default (function (isScrollAtTop, isScrollAtBottom, isScrollAtLeft, isScrollAtRight) {
  // Do lock for a wheel when scrolling
  var lockRef = useRef(false);
  var lockTimeoutRef = useRef(null);
  function lockScroll() {
    clearTimeout(lockTimeoutRef.current);
    lockRef.current = true;
    lockTimeoutRef.current = setTimeout(function () {
      lockRef.current = false;
    }, 50);
  }

  // Pass to ref since global add is in closure
  var scrollPingRef = useRef({
    top: isScrollAtTop,
    bottom: isScrollAtBottom,
    left: isScrollAtLeft,
    right: isScrollAtRight
  });
  scrollPingRef.current.top = isScrollAtTop;
  scrollPingRef.current.bottom = isScrollAtBottom;
  scrollPingRef.current.left = isScrollAtLeft;
  scrollPingRef.current.right = isScrollAtRight;
  return function (isHorizontal, delta) {
    var smoothOffset = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : false;
    var originScroll = isHorizontal ?
    // Pass origin wheel when on the left
    delta < 0 && scrollPingRef.current.left ||
    // Pass origin wheel when on the right
    delta > 0 && scrollPingRef.current.right // Pass origin wheel when on the top
    : delta < 0 && scrollPingRef.current.top ||
    // Pass origin wheel when on the bottom
    delta > 0 && scrollPingRef.current.bottom;
    if (smoothOffset && originScroll) {
      // No need lock anymore when it's smooth offset from touchMove interval
      clearTimeout(lockTimeoutRef.current);
      lockRef.current = false;
    } else if (!originScroll || lockRef.current) {
      lockScroll();
    }
    return !lockRef.current && originScroll;
  };
});