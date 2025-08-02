"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");
var _typeof3 = require("@babel/runtime/helpers/typeof");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var _defineProperty2 = _interopRequireDefault(require("@babel/runtime/helpers/defineProperty"));
var _typeof2 = _interopRequireDefault(require("@babel/runtime/helpers/typeof"));
var _slicedToArray2 = _interopRequireDefault(require("@babel/runtime/helpers/slicedToArray"));
var _classnames = _interopRequireDefault(require("classnames"));
var _KeyCode = _interopRequireDefault(require("rc-util/lib/KeyCode"));
var React = _interopRequireWildcard(require("react"));
var _pickAttrs = _interopRequireDefault(require("rc-util/lib/pickAttrs"));
function _getRequireWildcardCache(e) { if ("function" != typeof WeakMap) return null; var r = new WeakMap(), t = new WeakMap(); return (_getRequireWildcardCache = function _getRequireWildcardCache(e) { return e ? t : r; })(e); }
function _interopRequireWildcard(e, r) { if (!r && e && e.__esModule) return e; if (null === e || "object" != _typeof3(e) && "function" != typeof e) return { default: e }; var t = _getRequireWildcardCache(r); if (t && t.has(e)) return t.get(e); var n = { __proto__: null }, a = Object.defineProperty && Object.getOwnPropertyDescriptor; for (var u in e) if ("default" !== u && Object.prototype.hasOwnProperty.call(e, u)) { var i = a ? Object.getOwnPropertyDescriptor(e, u) : null; i && (i.get || i.set) ? Object.defineProperty(n, u, i) : n[u] = e[u]; } return n.default = e, t && t.set(e, n), n; }
var Notify = /*#__PURE__*/React.forwardRef(function (props, ref) {
  var prefixCls = props.prefixCls,
    style = props.style,
    className = props.className,
    _props$duration = props.duration,
    duration = _props$duration === void 0 ? 4.5 : _props$duration,
    showProgress = props.showProgress,
    _props$pauseOnHover = props.pauseOnHover,
    pauseOnHover = _props$pauseOnHover === void 0 ? true : _props$pauseOnHover,
    eventKey = props.eventKey,
    content = props.content,
    closable = props.closable,
    _props$closeIcon = props.closeIcon,
    closeIcon = _props$closeIcon === void 0 ? 'x' : _props$closeIcon,
    divProps = props.props,
    onClick = props.onClick,
    onNoticeClose = props.onNoticeClose,
    times = props.times,
    forcedHovering = props.hovering;
  var _React$useState = React.useState(false),
    _React$useState2 = (0, _slicedToArray2.default)(_React$useState, 2),
    hovering = _React$useState2[0],
    setHovering = _React$useState2[1];
  var _React$useState3 = React.useState(0),
    _React$useState4 = (0, _slicedToArray2.default)(_React$useState3, 2),
    percent = _React$useState4[0],
    setPercent = _React$useState4[1];
  var _React$useState5 = React.useState(0),
    _React$useState6 = (0, _slicedToArray2.default)(_React$useState5, 2),
    spentTime = _React$useState6[0],
    setSpentTime = _React$useState6[1];
  var mergedHovering = forcedHovering || hovering;
  var mergedShowProgress = duration > 0 && showProgress;

  // ======================== Close =========================
  var onInternalClose = function onInternalClose() {
    onNoticeClose(eventKey);
  };
  var onCloseKeyDown = function onCloseKeyDown(e) {
    if (e.key === 'Enter' || e.code === 'Enter' || e.keyCode === _KeyCode.default.ENTER) {
      onInternalClose();
    }
  };

  // ======================== Effect ========================
  React.useEffect(function () {
    if (!mergedHovering && duration > 0) {
      var start = Date.now() - spentTime;
      var timeout = setTimeout(function () {
        onInternalClose();
      }, duration * 1000 - spentTime);
      return function () {
        if (pauseOnHover) {
          clearTimeout(timeout);
        }
        setSpentTime(Date.now() - start);
      };
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [duration, mergedHovering, times]);
  React.useEffect(function () {
    if (!mergedHovering && mergedShowProgress && (pauseOnHover || spentTime === 0)) {
      var start = performance.now();
      var animationFrame;
      var calculate = function calculate() {
        cancelAnimationFrame(animationFrame);
        animationFrame = requestAnimationFrame(function (timestamp) {
          var runtime = timestamp + spentTime - start;
          var progress = Math.min(runtime / (duration * 1000), 1);
          setPercent(progress * 100);
          if (progress < 1) {
            calculate();
          }
        });
      };
      calculate();
      return function () {
        if (pauseOnHover) {
          cancelAnimationFrame(animationFrame);
        }
      };
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [duration, spentTime, mergedHovering, mergedShowProgress, times]);

  // ======================== Closable ========================
  var closableObj = React.useMemo(function () {
    if ((0, _typeof2.default)(closable) === 'object' && closable !== null) {
      return closable;
    }
    if (closable) {
      return {
        closeIcon: closeIcon
      };
    }
    return {};
  }, [closable, closeIcon]);
  var ariaProps = (0, _pickAttrs.default)(closableObj, true);

  // ======================== Progress ========================
  var validPercent = 100 - (!percent || percent < 0 ? 0 : percent > 100 ? 100 : percent);

  // ======================== Render ========================
  var noticePrefixCls = "".concat(prefixCls, "-notice");
  return /*#__PURE__*/React.createElement("div", (0, _extends2.default)({}, divProps, {
    ref: ref,
    className: (0, _classnames.default)(noticePrefixCls, className, (0, _defineProperty2.default)({}, "".concat(noticePrefixCls, "-closable"), closable)),
    style: style,
    onMouseEnter: function onMouseEnter(e) {
      var _divProps$onMouseEnte;
      setHovering(true);
      divProps === null || divProps === void 0 || (_divProps$onMouseEnte = divProps.onMouseEnter) === null || _divProps$onMouseEnte === void 0 || _divProps$onMouseEnte.call(divProps, e);
    },
    onMouseLeave: function onMouseLeave(e) {
      var _divProps$onMouseLeav;
      setHovering(false);
      divProps === null || divProps === void 0 || (_divProps$onMouseLeav = divProps.onMouseLeave) === null || _divProps$onMouseLeav === void 0 || _divProps$onMouseLeav.call(divProps, e);
    },
    onClick: onClick
  }), /*#__PURE__*/React.createElement("div", {
    className: "".concat(noticePrefixCls, "-content")
  }, content), closable && /*#__PURE__*/React.createElement("a", (0, _extends2.default)({
    tabIndex: 0,
    className: "".concat(noticePrefixCls, "-close"),
    onKeyDown: onCloseKeyDown,
    "aria-label": "Close"
  }, ariaProps, {
    onClick: function onClick(e) {
      e.preventDefault();
      e.stopPropagation();
      onInternalClose();
    }
  }), closableObj.closeIcon), mergedShowProgress && /*#__PURE__*/React.createElement("progress", {
    className: "".concat(noticePrefixCls, "-progress"),
    max: "100",
    value: validPercent
  }, validPercent + '%'));
});
var _default = exports.default = Notify;