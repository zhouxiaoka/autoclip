"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");
var _typeof = require("@babel/runtime/helpers/typeof");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = MotionThumb;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _slicedToArray2 = _interopRequireDefault(require("@babel/runtime/helpers/slicedToArray"));
var _classnames = _interopRequireDefault(require("classnames"));
var _rcMotion = _interopRequireDefault(require("rc-motion"));
var _useLayoutEffect = _interopRequireDefault(require("rc-util/lib/hooks/useLayoutEffect"));
var _ref2 = require("rc-util/lib/ref");
var React = _interopRequireWildcard(require("react"));
function _getRequireWildcardCache(e) { if ("function" != typeof WeakMap) return null; var r = new WeakMap(), t = new WeakMap(); return (_getRequireWildcardCache = function _getRequireWildcardCache(e) { return e ? t : r; })(e); }
function _interopRequireWildcard(e, r) { if (!r && e && e.__esModule) return e; if (null === e || "object" != _typeof(e) && "function" != typeof e) return { default: e }; var t = _getRequireWildcardCache(r); if (t && t.has(e)) return t.get(e); var n = { __proto__: null }, a = Object.defineProperty && Object.getOwnPropertyDescriptor; for (var u in e) if ("default" !== u && Object.prototype.hasOwnProperty.call(e, u)) { var i = a ? Object.getOwnPropertyDescriptor(e, u) : null; i && (i.get || i.set) ? Object.defineProperty(n, u, i) : n[u] = e[u]; } return n.default = e, t && t.set(e, n), n; }
var calcThumbStyle = function calcThumbStyle(targetElement, vertical) {
  if (!targetElement) return null;
  var style = {
    left: targetElement.offsetLeft,
    right: targetElement.parentElement.clientWidth - targetElement.clientWidth - targetElement.offsetLeft,
    width: targetElement.clientWidth,
    top: targetElement.offsetTop,
    bottom: targetElement.parentElement.clientHeight - targetElement.clientHeight - targetElement.offsetTop,
    height: targetElement.clientHeight
  };
  if (vertical) {
    // Adjusts positioning and size for vertical layout by setting horizontal properties to 0 and using vertical properties from the style object.
    return {
      left: 0,
      right: 0,
      width: 0,
      top: style.top,
      bottom: style.bottom,
      height: style.height
    };
  }
  return {
    left: style.left,
    right: style.right,
    width: style.width,
    top: 0,
    bottom: 0,
    height: 0
  };
};
var toPX = function toPX(value) {
  return value !== undefined ? "".concat(value, "px") : undefined;
};
function MotionThumb(props) {
  var prefixCls = props.prefixCls,
    containerRef = props.containerRef,
    value = props.value,
    getValueIndex = props.getValueIndex,
    motionName = props.motionName,
    onMotionStart = props.onMotionStart,
    onMotionEnd = props.onMotionEnd,
    direction = props.direction,
    _props$vertical = props.vertical,
    vertical = _props$vertical === void 0 ? false : _props$vertical;
  var thumbRef = React.useRef(null);
  var _React$useState = React.useState(value),
    _React$useState2 = (0, _slicedToArray2.default)(_React$useState, 2),
    prevValue = _React$useState2[0],
    setPrevValue = _React$useState2[1];

  // =========================== Effect ===========================
  var findValueElement = function findValueElement(val) {
    var _containerRef$current;
    var index = getValueIndex(val);
    var ele = (_containerRef$current = containerRef.current) === null || _containerRef$current === void 0 ? void 0 : _containerRef$current.querySelectorAll(".".concat(prefixCls, "-item"))[index];
    return (ele === null || ele === void 0 ? void 0 : ele.offsetParent) && ele;
  };
  var _React$useState3 = React.useState(null),
    _React$useState4 = (0, _slicedToArray2.default)(_React$useState3, 2),
    prevStyle = _React$useState4[0],
    setPrevStyle = _React$useState4[1];
  var _React$useState5 = React.useState(null),
    _React$useState6 = (0, _slicedToArray2.default)(_React$useState5, 2),
    nextStyle = _React$useState6[0],
    setNextStyle = _React$useState6[1];
  (0, _useLayoutEffect.default)(function () {
    if (prevValue !== value) {
      var prev = findValueElement(prevValue);
      var next = findValueElement(value);
      var calcPrevStyle = calcThumbStyle(prev, vertical);
      var calcNextStyle = calcThumbStyle(next, vertical);
      setPrevValue(value);
      setPrevStyle(calcPrevStyle);
      setNextStyle(calcNextStyle);
      if (prev && next) {
        onMotionStart();
      } else {
        onMotionEnd();
      }
    }
  }, [value]);
  var thumbStart = React.useMemo(function () {
    if (vertical) {
      var _prevStyle$top;
      return toPX((_prevStyle$top = prevStyle === null || prevStyle === void 0 ? void 0 : prevStyle.top) !== null && _prevStyle$top !== void 0 ? _prevStyle$top : 0);
    }
    if (direction === 'rtl') {
      return toPX(-(prevStyle === null || prevStyle === void 0 ? void 0 : prevStyle.right));
    }
    return toPX(prevStyle === null || prevStyle === void 0 ? void 0 : prevStyle.left);
  }, [vertical, direction, prevStyle]);
  var thumbActive = React.useMemo(function () {
    if (vertical) {
      var _nextStyle$top;
      return toPX((_nextStyle$top = nextStyle === null || nextStyle === void 0 ? void 0 : nextStyle.top) !== null && _nextStyle$top !== void 0 ? _nextStyle$top : 0);
    }
    if (direction === 'rtl') {
      return toPX(-(nextStyle === null || nextStyle === void 0 ? void 0 : nextStyle.right));
    }
    return toPX(nextStyle === null || nextStyle === void 0 ? void 0 : nextStyle.left);
  }, [vertical, direction, nextStyle]);

  // =========================== Motion ===========================
  var onAppearStart = function onAppearStart() {
    if (vertical) {
      return {
        transform: 'translateY(var(--thumb-start-top))',
        height: 'var(--thumb-start-height)'
      };
    }
    return {
      transform: 'translateX(var(--thumb-start-left))',
      width: 'var(--thumb-start-width)'
    };
  };
  var onAppearActive = function onAppearActive() {
    if (vertical) {
      return {
        transform: 'translateY(var(--thumb-active-top))',
        height: 'var(--thumb-active-height)'
      };
    }
    return {
      transform: 'translateX(var(--thumb-active-left))',
      width: 'var(--thumb-active-width)'
    };
  };
  var onVisibleChanged = function onVisibleChanged() {
    setPrevStyle(null);
    setNextStyle(null);
    onMotionEnd();
  };

  // =========================== Render ===========================
  // No need motion when nothing exist in queue
  if (!prevStyle || !nextStyle) {
    return null;
  }
  return /*#__PURE__*/React.createElement(_rcMotion.default, {
    visible: true,
    motionName: motionName,
    motionAppear: true,
    onAppearStart: onAppearStart,
    onAppearActive: onAppearActive,
    onVisibleChanged: onVisibleChanged
  }, function (_ref, ref) {
    var motionClassName = _ref.className,
      motionStyle = _ref.style;
    var mergedStyle = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, motionStyle), {}, {
      '--thumb-start-left': thumbStart,
      '--thumb-start-width': toPX(prevStyle === null || prevStyle === void 0 ? void 0 : prevStyle.width),
      '--thumb-active-left': thumbActive,
      '--thumb-active-width': toPX(nextStyle === null || nextStyle === void 0 ? void 0 : nextStyle.width),
      '--thumb-start-top': thumbStart,
      '--thumb-start-height': toPX(prevStyle === null || prevStyle === void 0 ? void 0 : prevStyle.height),
      '--thumb-active-top': thumbActive,
      '--thumb-active-height': toPX(nextStyle === null || nextStyle === void 0 ? void 0 : nextStyle.height)
    });

    // It's little ugly which should be refactor when @umi/test update to latest jsdom
    var motionProps = {
      ref: (0, _ref2.composeRef)(thumbRef, ref),
      style: mergedStyle,
      className: (0, _classnames.default)("".concat(prefixCls, "-thumb"), motionClassName)
    };
    if (process.env.NODE_ENV === 'test') {
      motionProps['data-test-style'] = JSON.stringify(mergedStyle);
    }
    return /*#__PURE__*/React.createElement("div", motionProps);
  });
}