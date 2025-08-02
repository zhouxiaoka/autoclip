import _extends from "@babel/runtime/helpers/esm/extends";
import _typeof from "@babel/runtime/helpers/esm/typeof";
import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import _defineProperty from "@babel/runtime/helpers/esm/defineProperty";
import _slicedToArray from "@babel/runtime/helpers/esm/slicedToArray";
import _objectWithoutProperties from "@babel/runtime/helpers/esm/objectWithoutProperties";
var _excluded = ["prefixCls", "className", "height", "itemHeight", "fullHeight", "style", "data", "children", "itemKey", "virtual", "direction", "scrollWidth", "component", "onScroll", "onVirtualScroll", "onVisibleChange", "innerProps", "extraRender", "styles", "showScrollBar"];
import classNames from 'classnames';
import ResizeObserver from 'rc-resize-observer';
import { useEvent } from 'rc-util';
import useLayoutEffect from "rc-util/es/hooks/useLayoutEffect";
import * as React from 'react';
import { useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import Filler from "./Filler";
import useChildren from "./hooks/useChildren";
import useDiffItem from "./hooks/useDiffItem";
import useFrameWheel from "./hooks/useFrameWheel";
import { useGetSize } from "./hooks/useGetSize";
import useHeights from "./hooks/useHeights";
import useMobileTouchMove from "./hooks/useMobileTouchMove";
import useOriginScroll from "./hooks/useOriginScroll";
import useScrollDrag from "./hooks/useScrollDrag";
import useScrollTo from "./hooks/useScrollTo";
import ScrollBar from "./ScrollBar";
import { getSpinSize } from "./utils/scrollbarUtil";
var EMPTY_DATA = [];
var ScrollStyle = {
  overflowY: 'auto',
  overflowAnchor: 'none'
};
export function RawList(props, ref) {
  var _props$prefixCls = props.prefixCls,
    prefixCls = _props$prefixCls === void 0 ? 'rc-virtual-list' : _props$prefixCls,
    className = props.className,
    height = props.height,
    itemHeight = props.itemHeight,
    _props$fullHeight = props.fullHeight,
    fullHeight = _props$fullHeight === void 0 ? true : _props$fullHeight,
    style = props.style,
    data = props.data,
    children = props.children,
    itemKey = props.itemKey,
    virtual = props.virtual,
    direction = props.direction,
    scrollWidth = props.scrollWidth,
    _props$component = props.component,
    Component = _props$component === void 0 ? 'div' : _props$component,
    onScroll = props.onScroll,
    onVirtualScroll = props.onVirtualScroll,
    onVisibleChange = props.onVisibleChange,
    innerProps = props.innerProps,
    extraRender = props.extraRender,
    styles = props.styles,
    _props$showScrollBar = props.showScrollBar,
    showScrollBar = _props$showScrollBar === void 0 ? 'optional' : _props$showScrollBar,
    restProps = _objectWithoutProperties(props, _excluded);

  // =============================== Item Key ===============================
  var getKey = React.useCallback(function (item) {
    if (typeof itemKey === 'function') {
      return itemKey(item);
    }
    return item === null || item === void 0 ? void 0 : item[itemKey];
  }, [itemKey]);

  // ================================ Height ================================
  var _useHeights = useHeights(getKey, null, null),
    _useHeights2 = _slicedToArray(_useHeights, 4),
    setInstanceRef = _useHeights2[0],
    collectHeight = _useHeights2[1],
    heights = _useHeights2[2],
    heightUpdatedMark = _useHeights2[3];

  // ================================= MISC =================================
  var useVirtual = !!(virtual !== false && height && itemHeight);
  var containerHeight = React.useMemo(function () {
    return Object.values(heights.maps).reduce(function (total, curr) {
      return total + curr;
    }, 0);
  }, [heights.id, heights.maps]);
  var inVirtual = useVirtual && data && (Math.max(itemHeight * data.length, containerHeight) > height || !!scrollWidth);
  var isRTL = direction === 'rtl';
  var mergedClassName = classNames(prefixCls, _defineProperty({}, "".concat(prefixCls, "-rtl"), isRTL), className);
  var mergedData = data || EMPTY_DATA;
  var componentRef = useRef();
  var fillerInnerRef = useRef();
  var containerRef = useRef();

  // =============================== Item Key ===============================

  var _useState = useState(0),
    _useState2 = _slicedToArray(_useState, 2),
    offsetTop = _useState2[0],
    setOffsetTop = _useState2[1];
  var _useState3 = useState(0),
    _useState4 = _slicedToArray(_useState3, 2),
    offsetLeft = _useState4[0],
    setOffsetLeft = _useState4[1];
  var _useState5 = useState(false),
    _useState6 = _slicedToArray(_useState5, 2),
    scrollMoving = _useState6[0],
    setScrollMoving = _useState6[1];
  var onScrollbarStartMove = function onScrollbarStartMove() {
    setScrollMoving(true);
  };
  var onScrollbarStopMove = function onScrollbarStopMove() {
    setScrollMoving(false);
  };
  var sharedConfig = {
    getKey: getKey
  };

  // ================================ Scroll ================================
  function syncScrollTop(newTop) {
    setOffsetTop(function (origin) {
      var value;
      if (typeof newTop === 'function') {
        value = newTop(origin);
      } else {
        value = newTop;
      }
      var alignedTop = keepInRange(value);
      componentRef.current.scrollTop = alignedTop;
      return alignedTop;
    });
  }

  // ================================ Legacy ================================
  // Put ref here since the range is generate by follow
  var rangeRef = useRef({
    start: 0,
    end: mergedData.length
  });
  var diffItemRef = useRef();
  var _useDiffItem = useDiffItem(mergedData, getKey),
    _useDiffItem2 = _slicedToArray(_useDiffItem, 1),
    diffItem = _useDiffItem2[0];
  diffItemRef.current = diffItem;

  // ========================== Visible Calculation =========================
  var _React$useMemo = React.useMemo(function () {
      if (!useVirtual) {
        return {
          scrollHeight: undefined,
          start: 0,
          end: mergedData.length - 1,
          offset: undefined
        };
      }

      // Always use virtual scroll bar in avoid shaking
      if (!inVirtual) {
        var _fillerInnerRef$curre;
        return {
          scrollHeight: ((_fillerInnerRef$curre = fillerInnerRef.current) === null || _fillerInnerRef$curre === void 0 ? void 0 : _fillerInnerRef$curre.offsetHeight) || 0,
          start: 0,
          end: mergedData.length - 1,
          offset: undefined
        };
      }
      var itemTop = 0;
      var startIndex;
      var startOffset;
      var endIndex;
      var dataLen = mergedData.length;
      for (var i = 0; i < dataLen; i += 1) {
        var _item = mergedData[i];
        var key = getKey(_item);
        var cacheHeight = heights.get(key);
        var currentItemBottom = itemTop + (cacheHeight === undefined ? itemHeight : cacheHeight);

        // Check item top in the range
        if (currentItemBottom >= offsetTop && startIndex === undefined) {
          startIndex = i;
          startOffset = itemTop;
        }

        // Check item bottom in the range. We will render additional one item for motion usage
        if (currentItemBottom > offsetTop + height && endIndex === undefined) {
          endIndex = i;
        }
        itemTop = currentItemBottom;
      }

      // When scrollTop at the end but data cut to small count will reach this
      if (startIndex === undefined) {
        startIndex = 0;
        startOffset = 0;
        endIndex = Math.ceil(height / itemHeight);
      }
      if (endIndex === undefined) {
        endIndex = mergedData.length - 1;
      }

      // Give cache to improve scroll experience
      endIndex = Math.min(endIndex + 1, mergedData.length - 1);
      return {
        scrollHeight: itemTop,
        start: startIndex,
        end: endIndex,
        offset: startOffset
      };
    }, [inVirtual, useVirtual, offsetTop, mergedData, heightUpdatedMark, height]),
    scrollHeight = _React$useMemo.scrollHeight,
    start = _React$useMemo.start,
    end = _React$useMemo.end,
    fillerOffset = _React$useMemo.offset;
  rangeRef.current.start = start;
  rangeRef.current.end = end;

  // When scroll up, first visible item get real height may not same as `itemHeight`,
  // Which will make scroll jump.
  // Let's sync scroll top to avoid jump
  React.useLayoutEffect(function () {
    var changedRecord = heights.getRecord();
    if (changedRecord.size === 1) {
      var recordKey = Array.from(changedRecord.keys())[0];
      var prevCacheHeight = changedRecord.get(recordKey);

      // Quick switch data may cause `start` not in `mergedData` anymore
      var startItem = mergedData[start];
      if (startItem && prevCacheHeight === undefined) {
        var startIndexKey = getKey(startItem);
        if (startIndexKey === recordKey) {
          var realStartHeight = heights.get(recordKey);
          var diffHeight = realStartHeight - itemHeight;
          syncScrollTop(function (ori) {
            return ori + diffHeight;
          });
        }
      }
    }
    heights.resetRecord();
  }, [scrollHeight]);

  // ================================= Size =================================
  var _React$useState = React.useState({
      width: 0,
      height: height
    }),
    _React$useState2 = _slicedToArray(_React$useState, 2),
    size = _React$useState2[0],
    setSize = _React$useState2[1];
  var onHolderResize = function onHolderResize(sizeInfo) {
    setSize({
      width: sizeInfo.offsetWidth,
      height: sizeInfo.offsetHeight
    });
  };

  // Hack on scrollbar to enable flash call
  var verticalScrollBarRef = useRef();
  var horizontalScrollBarRef = useRef();
  var horizontalScrollBarSpinSize = React.useMemo(function () {
    return getSpinSize(size.width, scrollWidth);
  }, [size.width, scrollWidth]);
  var verticalScrollBarSpinSize = React.useMemo(function () {
    return getSpinSize(size.height, scrollHeight);
  }, [size.height, scrollHeight]);

  // =============================== In Range ===============================
  var maxScrollHeight = scrollHeight - height;
  var maxScrollHeightRef = useRef(maxScrollHeight);
  maxScrollHeightRef.current = maxScrollHeight;
  function keepInRange(newScrollTop) {
    var newTop = newScrollTop;
    if (!Number.isNaN(maxScrollHeightRef.current)) {
      newTop = Math.min(newTop, maxScrollHeightRef.current);
    }
    newTop = Math.max(newTop, 0);
    return newTop;
  }
  var isScrollAtTop = offsetTop <= 0;
  var isScrollAtBottom = offsetTop >= maxScrollHeight;
  var isScrollAtLeft = offsetLeft <= 0;
  var isScrollAtRight = offsetLeft >= scrollWidth;
  var originScroll = useOriginScroll(isScrollAtTop, isScrollAtBottom, isScrollAtLeft, isScrollAtRight);

  // ================================ Scroll ================================
  var getVirtualScrollInfo = function getVirtualScrollInfo() {
    return {
      x: isRTL ? -offsetLeft : offsetLeft,
      y: offsetTop
    };
  };
  var lastVirtualScrollInfoRef = useRef(getVirtualScrollInfo());
  var triggerScroll = useEvent(function (params) {
    if (onVirtualScroll) {
      var nextInfo = _objectSpread(_objectSpread({}, getVirtualScrollInfo()), params);

      // Trigger when offset changed
      if (lastVirtualScrollInfoRef.current.x !== nextInfo.x || lastVirtualScrollInfoRef.current.y !== nextInfo.y) {
        onVirtualScroll(nextInfo);
        lastVirtualScrollInfoRef.current = nextInfo;
      }
    }
  });
  function onScrollBar(newScrollOffset, horizontal) {
    var newOffset = newScrollOffset;
    if (horizontal) {
      flushSync(function () {
        setOffsetLeft(newOffset);
      });
      triggerScroll();
    } else {
      syncScrollTop(newOffset);
    }
  }

  // When data size reduce. It may trigger native scroll event back to fit scroll position
  function onFallbackScroll(e) {
    var newScrollTop = e.currentTarget.scrollTop;
    if (newScrollTop !== offsetTop) {
      syncScrollTop(newScrollTop);
    }

    // Trigger origin onScroll
    onScroll === null || onScroll === void 0 || onScroll(e);
    triggerScroll();
  }
  var keepInHorizontalRange = function keepInHorizontalRange(nextOffsetLeft) {
    var tmpOffsetLeft = nextOffsetLeft;
    var max = !!scrollWidth ? scrollWidth - size.width : 0;
    tmpOffsetLeft = Math.max(tmpOffsetLeft, 0);
    tmpOffsetLeft = Math.min(tmpOffsetLeft, max);
    return tmpOffsetLeft;
  };
  var onWheelDelta = useEvent(function (offsetXY, fromHorizontal) {
    if (fromHorizontal) {
      flushSync(function () {
        setOffsetLeft(function (left) {
          var nextOffsetLeft = left + (isRTL ? -offsetXY : offsetXY);
          return keepInHorizontalRange(nextOffsetLeft);
        });
      });
      triggerScroll();
    } else {
      syncScrollTop(function (top) {
        var newTop = top + offsetXY;
        return newTop;
      });
    }
  });

  // Since this added in global,should use ref to keep update
  var _useFrameWheel = useFrameWheel(useVirtual, isScrollAtTop, isScrollAtBottom, isScrollAtLeft, isScrollAtRight, !!scrollWidth, onWheelDelta),
    _useFrameWheel2 = _slicedToArray(_useFrameWheel, 2),
    onRawWheel = _useFrameWheel2[0],
    onFireFoxScroll = _useFrameWheel2[1];

  // Mobile touch move
  useMobileTouchMove(useVirtual, componentRef, function (isHorizontal, delta, smoothOffset, e) {
    var event = e;
    if (originScroll(isHorizontal, delta, smoothOffset)) {
      return false;
    }

    // Fix nest List trigger TouchMove event
    if (!event || !event._virtualHandled) {
      if (event) {
        event._virtualHandled = true;
      }
      onRawWheel({
        preventDefault: function preventDefault() {},
        deltaX: isHorizontal ? delta : 0,
        deltaY: isHorizontal ? 0 : delta
      });
      return true;
    }
    return false;
  });

  // MouseDown drag for scroll
  useScrollDrag(inVirtual, componentRef, function (offset) {
    syncScrollTop(function (top) {
      return top + offset;
    });
  });
  useLayoutEffect(function () {
    // Firefox only
    function onMozMousePixelScroll(e) {
      // scrolling at top/bottom limit
      var scrollingUpAtTop = isScrollAtTop && e.detail < 0;
      var scrollingDownAtBottom = isScrollAtBottom && e.detail > 0;
      if (useVirtual && !scrollingUpAtTop && !scrollingDownAtBottom) {
        e.preventDefault();
      }
    }
    var componentEle = componentRef.current;
    componentEle.addEventListener('wheel', onRawWheel, {
      passive: false
    });
    componentEle.addEventListener('DOMMouseScroll', onFireFoxScroll, {
      passive: true
    });
    componentEle.addEventListener('MozMousePixelScroll', onMozMousePixelScroll, {
      passive: false
    });
    return function () {
      componentEle.removeEventListener('wheel', onRawWheel);
      componentEle.removeEventListener('DOMMouseScroll', onFireFoxScroll);
      componentEle.removeEventListener('MozMousePixelScroll', onMozMousePixelScroll);
    };
  }, [useVirtual, isScrollAtTop, isScrollAtBottom]);

  // Sync scroll left
  useLayoutEffect(function () {
    if (scrollWidth) {
      var newOffsetLeft = keepInHorizontalRange(offsetLeft);
      setOffsetLeft(newOffsetLeft);
      triggerScroll({
        x: newOffsetLeft
      });
    }
  }, [size.width, scrollWidth]);

  // ================================= Ref ==================================
  var delayHideScrollBar = function delayHideScrollBar() {
    var _verticalScrollBarRef, _horizontalScrollBarR;
    (_verticalScrollBarRef = verticalScrollBarRef.current) === null || _verticalScrollBarRef === void 0 || _verticalScrollBarRef.delayHidden();
    (_horizontalScrollBarR = horizontalScrollBarRef.current) === null || _horizontalScrollBarR === void 0 || _horizontalScrollBarR.delayHidden();
  };
  var _scrollTo = useScrollTo(componentRef, mergedData, heights, itemHeight, getKey, function () {
    return collectHeight(true);
  }, syncScrollTop, delayHideScrollBar);
  React.useImperativeHandle(ref, function () {
    return {
      nativeElement: containerRef.current,
      getScrollInfo: getVirtualScrollInfo,
      scrollTo: function scrollTo(config) {
        function isPosScroll(arg) {
          return arg && _typeof(arg) === 'object' && ('left' in arg || 'top' in arg);
        }
        if (isPosScroll(config)) {
          // Scroll X
          if (config.left !== undefined) {
            setOffsetLeft(keepInHorizontalRange(config.left));
          }

          // Scroll Y
          _scrollTo(config.top);
        } else {
          _scrollTo(config);
        }
      }
    };
  });

  // ================================ Effect ================================
  /** We need told outside that some list not rendered */
  useLayoutEffect(function () {
    if (onVisibleChange) {
      var renderList = mergedData.slice(start, end + 1);
      onVisibleChange(renderList, mergedData);
    }
  }, [start, end, mergedData]);

  // ================================ Extra =================================
  var getSize = useGetSize(mergedData, getKey, heights, itemHeight);
  var extraContent = extraRender === null || extraRender === void 0 ? void 0 : extraRender({
    start: start,
    end: end,
    virtual: inVirtual,
    offsetX: offsetLeft,
    offsetY: fillerOffset,
    rtl: isRTL,
    getSize: getSize
  });

  // ================================ Render ================================
  var listChildren = useChildren(mergedData, start, end, scrollWidth, offsetLeft, setInstanceRef, children, sharedConfig);
  var componentStyle = null;
  if (height) {
    componentStyle = _objectSpread(_defineProperty({}, fullHeight ? 'height' : 'maxHeight', height), ScrollStyle);
    if (useVirtual) {
      componentStyle.overflowY = 'hidden';
      if (scrollWidth) {
        componentStyle.overflowX = 'hidden';
      }
      if (scrollMoving) {
        componentStyle.pointerEvents = 'none';
      }
    }
  }
  var containerProps = {};
  if (isRTL) {
    containerProps.dir = 'rtl';
  }
  return /*#__PURE__*/React.createElement("div", _extends({
    ref: containerRef,
    style: _objectSpread(_objectSpread({}, style), {}, {
      position: 'relative'
    }),
    className: mergedClassName
  }, containerProps, restProps), /*#__PURE__*/React.createElement(ResizeObserver, {
    onResize: onHolderResize
  }, /*#__PURE__*/React.createElement(Component, {
    className: "".concat(prefixCls, "-holder"),
    style: componentStyle,
    ref: componentRef,
    onScroll: onFallbackScroll,
    onMouseEnter: delayHideScrollBar
  }, /*#__PURE__*/React.createElement(Filler, {
    prefixCls: prefixCls,
    height: scrollHeight,
    offsetX: offsetLeft,
    offsetY: fillerOffset,
    scrollWidth: scrollWidth,
    onInnerResize: collectHeight,
    ref: fillerInnerRef,
    innerProps: innerProps,
    rtl: isRTL,
    extra: extraContent
  }, listChildren))), inVirtual && scrollHeight > height && /*#__PURE__*/React.createElement(ScrollBar, {
    ref: verticalScrollBarRef,
    prefixCls: prefixCls,
    scrollOffset: offsetTop,
    scrollRange: scrollHeight,
    rtl: isRTL,
    onScroll: onScrollBar,
    onStartMove: onScrollbarStartMove,
    onStopMove: onScrollbarStopMove,
    spinSize: verticalScrollBarSpinSize,
    containerSize: size.height,
    style: styles === null || styles === void 0 ? void 0 : styles.verticalScrollBar,
    thumbStyle: styles === null || styles === void 0 ? void 0 : styles.verticalScrollBarThumb,
    showScrollBar: showScrollBar
  }), inVirtual && scrollWidth > size.width && /*#__PURE__*/React.createElement(ScrollBar, {
    ref: horizontalScrollBarRef,
    prefixCls: prefixCls,
    scrollOffset: offsetLeft,
    scrollRange: scrollWidth,
    rtl: isRTL,
    onScroll: onScrollBar,
    onStartMove: onScrollbarStartMove,
    onStopMove: onScrollbarStopMove,
    spinSize: horizontalScrollBarSpinSize,
    containerSize: size.width,
    horizontal: true,
    style: styles === null || styles === void 0 ? void 0 : styles.horizontalScrollBar,
    thumbStyle: styles === null || styles === void 0 ? void 0 : styles.horizontalScrollBarThumb,
    showScrollBar: showScrollBar
  }));
}
var List = /*#__PURE__*/React.forwardRef(RawList);
List.displayName = 'List';
export default List;