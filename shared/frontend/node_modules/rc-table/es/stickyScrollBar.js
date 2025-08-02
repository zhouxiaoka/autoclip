import _defineProperty from "@babel/runtime/helpers/esm/defineProperty";
import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import _slicedToArray from "@babel/runtime/helpers/esm/slicedToArray";
import { useContext } from '@rc-component/context';
import classNames from 'classnames';
import addEventListener from "rc-util/es/Dom/addEventListener";
import getScrollBarSize from "rc-util/es/getScrollBarSize";
import * as React from 'react';
import TableContext from "./context/TableContext";
import { useLayoutState } from "./hooks/useFrame";
import raf from "rc-util/es/raf";
import { getOffset } from "./utils/offsetUtil";
import { getDOM } from "rc-util/es/Dom/findDOMNode";
var StickyScrollBar = function StickyScrollBar(_ref, ref) {
  var _scrollBodyRef$curren, _scrollBodyRef$curren2;
  var scrollBodyRef = _ref.scrollBodyRef,
    onScroll = _ref.onScroll,
    offsetScroll = _ref.offsetScroll,
    container = _ref.container,
    direction = _ref.direction;
  var prefixCls = useContext(TableContext, 'prefixCls');
  var bodyScrollWidth = ((_scrollBodyRef$curren = scrollBodyRef.current) === null || _scrollBodyRef$curren === void 0 ? void 0 : _scrollBodyRef$curren.scrollWidth) || 0;
  var bodyWidth = ((_scrollBodyRef$curren2 = scrollBodyRef.current) === null || _scrollBodyRef$curren2 === void 0 ? void 0 : _scrollBodyRef$curren2.clientWidth) || 0;
  var scrollBarWidth = bodyScrollWidth && bodyWidth * (bodyWidth / bodyScrollWidth);
  var scrollBarRef = React.useRef();
  var _useLayoutState = useLayoutState({
      scrollLeft: 0,
      isHiddenScrollBar: true
    }),
    _useLayoutState2 = _slicedToArray(_useLayoutState, 2),
    scrollState = _useLayoutState2[0],
    setScrollState = _useLayoutState2[1];
  var refState = React.useRef({
    delta: 0,
    x: 0
  });
  var _React$useState = React.useState(false),
    _React$useState2 = _slicedToArray(_React$useState, 2),
    isActive = _React$useState2[0],
    setActive = _React$useState2[1];
  var rafRef = React.useRef(null);
  React.useEffect(function () {
    return function () {
      raf.cancel(rafRef.current);
    };
  }, []);
  var onMouseUp = function onMouseUp() {
    setActive(false);
  };
  var onMouseDown = function onMouseDown(event) {
    event.persist();
    refState.current.delta = event.pageX - scrollState.scrollLeft;
    refState.current.x = 0;
    setActive(true);
    event.preventDefault();
  };
  var onMouseMove = function onMouseMove(event) {
    var _window;
    // https://developer.mozilla.org/en-US/docs/Web/API/MouseEvent/buttons
    var _ref2 = event || ((_window = window) === null || _window === void 0 ? void 0 : _window.event),
      buttons = _ref2.buttons;
    if (!isActive || buttons === 0) {
      // If out body mouse up, we can set isActive false when mouse move
      if (isActive) {
        setActive(false);
      }
      return;
    }
    var left = refState.current.x + event.pageX - refState.current.x - refState.current.delta;
    var isRTL = direction === 'rtl';
    // Limit scroll range
    left = Math.max(isRTL ? scrollBarWidth - bodyWidth : 0, Math.min(isRTL ? 0 : bodyWidth - scrollBarWidth, left));
    // Calculate the scroll position and update
    var shouldScroll = !isRTL || Math.abs(left) + Math.abs(scrollBarWidth) < bodyWidth;
    if (shouldScroll) {
      onScroll({
        scrollLeft: left / bodyWidth * (bodyScrollWidth + 2)
      });
      refState.current.x = event.pageX;
    }
  };
  var checkScrollBarVisible = function checkScrollBarVisible() {
    raf.cancel(rafRef.current);
    rafRef.current = raf(function () {
      if (!scrollBodyRef.current) {
        return;
      }
      var tableOffsetTop = getOffset(scrollBodyRef.current).top;
      var tableBottomOffset = tableOffsetTop + scrollBodyRef.current.offsetHeight;
      var currentClientOffset = container === window ? document.documentElement.scrollTop + window.innerHeight : getOffset(container).top + container.clientHeight;
      if (tableBottomOffset - getScrollBarSize() <= currentClientOffset || tableOffsetTop >= currentClientOffset - offsetScroll) {
        setScrollState(function (state) {
          return _objectSpread(_objectSpread({}, state), {}, {
            isHiddenScrollBar: true
          });
        });
      } else {
        setScrollState(function (state) {
          return _objectSpread(_objectSpread({}, state), {}, {
            isHiddenScrollBar: false
          });
        });
      }
    });
  };
  var setScrollLeft = function setScrollLeft(left) {
    setScrollState(function (state) {
      return _objectSpread(_objectSpread({}, state), {}, {
        scrollLeft: left / bodyScrollWidth * bodyWidth || 0
      });
    });
  };
  React.useImperativeHandle(ref, function () {
    return {
      setScrollLeft: setScrollLeft,
      checkScrollBarVisible: checkScrollBarVisible
    };
  });
  React.useEffect(function () {
    var onMouseUpListener = addEventListener(document.body, 'mouseup', onMouseUp, false);
    var onMouseMoveListener = addEventListener(document.body, 'mousemove', onMouseMove, false);
    checkScrollBarVisible();
    return function () {
      onMouseUpListener.remove();
      onMouseMoveListener.remove();
    };
  }, [scrollBarWidth, isActive]);

  // Loop for scroll event check
  React.useEffect(function () {
    if (!scrollBodyRef.current) return;
    var scrollParents = [];
    var parent = getDOM(scrollBodyRef.current);
    while (parent) {
      scrollParents.push(parent);
      parent = parent.parentElement;
    }
    scrollParents.forEach(function (p) {
      return p.addEventListener('scroll', checkScrollBarVisible, false);
    });
    window.addEventListener('resize', checkScrollBarVisible, false);
    window.addEventListener('scroll', checkScrollBarVisible, false);
    container.addEventListener('scroll', checkScrollBarVisible, false);
    return function () {
      scrollParents.forEach(function (p) {
        return p.removeEventListener('scroll', checkScrollBarVisible);
      });
      window.removeEventListener('resize', checkScrollBarVisible);
      window.removeEventListener('scroll', checkScrollBarVisible);
      container.removeEventListener('scroll', checkScrollBarVisible);
    };
  }, [container]);
  React.useEffect(function () {
    if (!scrollState.isHiddenScrollBar) {
      setScrollState(function (state) {
        var bodyNode = scrollBodyRef.current;
        if (!bodyNode) {
          return state;
        }
        return _objectSpread(_objectSpread({}, state), {}, {
          scrollLeft: bodyNode.scrollLeft / bodyNode.scrollWidth * bodyNode.clientWidth
        });
      });
    }
  }, [scrollState.isHiddenScrollBar]);
  if (bodyScrollWidth <= bodyWidth || !scrollBarWidth || scrollState.isHiddenScrollBar) {
    return null;
  }
  return /*#__PURE__*/React.createElement("div", {
    style: {
      height: getScrollBarSize(),
      width: bodyWidth,
      bottom: offsetScroll
    },
    className: "".concat(prefixCls, "-sticky-scroll")
  }, /*#__PURE__*/React.createElement("div", {
    onMouseDown: onMouseDown,
    ref: scrollBarRef,
    className: classNames("".concat(prefixCls, "-sticky-scroll-bar"), _defineProperty({}, "".concat(prefixCls, "-sticky-scroll-bar-active"), isActive)),
    style: {
      width: "".concat(scrollBarWidth, "px"),
      transform: "translate3d(".concat(scrollState.scrollLeft, "px, 0, 0)")
    }
  }));
};
export default /*#__PURE__*/React.forwardRef(StickyScrollBar);