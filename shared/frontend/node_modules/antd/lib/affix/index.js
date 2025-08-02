"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _react = _interopRequireDefault(require("react"));
var _classnames = _interopRequireDefault(require("classnames"));
var _rcResizeObserver = _interopRequireDefault(require("rc-resize-observer"));
var _throttleByAnimationFrame = _interopRequireDefault(require("../_util/throttleByAnimationFrame"));
var _configProvider = require("../config-provider");
var _style = _interopRequireDefault(require("./style"));
var _utils = require("./utils");
var __rest = void 0 && (void 0).__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
const TRIGGER_EVENTS = ['resize', 'scroll', 'touchstart', 'touchmove', 'touchend', 'pageshow', 'load'];
function getDefaultTarget() {
  return typeof window !== 'undefined' ? window : null;
}
const AFFIX_STATUS_NONE = 0;
const AFFIX_STATUS_PREPARE = 1;
const Affix = /*#__PURE__*/_react.default.forwardRef((props, ref) => {
  var _a;
  const {
      style,
      offsetTop,
      offsetBottom,
      prefixCls,
      className,
      rootClassName,
      children,
      target,
      onChange,
      onTestUpdatePosition
    } = props,
    restProps = __rest(props, ["style", "offsetTop", "offsetBottom", "prefixCls", "className", "rootClassName", "children", "target", "onChange", "onTestUpdatePosition"]);
  const {
    getPrefixCls,
    getTargetContainer
  } = _react.default.useContext(_configProvider.ConfigContext);
  const affixPrefixCls = getPrefixCls('affix', prefixCls);
  const [lastAffix, setLastAffix] = _react.default.useState(false);
  const [affixStyle, setAffixStyle] = _react.default.useState();
  const [placeholderStyle, setPlaceholderStyle] = _react.default.useState();
  const status = _react.default.useRef(AFFIX_STATUS_NONE);
  const prevTarget = _react.default.useRef(null);
  const prevListener = _react.default.useRef(null);
  const placeholderNodeRef = _react.default.useRef(null);
  const fixedNodeRef = _react.default.useRef(null);
  const timer = _react.default.useRef(null);
  const targetFunc = (_a = target !== null && target !== void 0 ? target : getTargetContainer) !== null && _a !== void 0 ? _a : getDefaultTarget;
  const internalOffsetTop = offsetBottom === undefined && offsetTop === undefined ? 0 : offsetTop;
  // =================== Measure ===================
  const measure = () => {
    if (status.current !== AFFIX_STATUS_PREPARE || !fixedNodeRef.current || !placeholderNodeRef.current || !targetFunc) {
      return;
    }
    const targetNode = targetFunc();
    if (targetNode) {
      const newState = {
        status: AFFIX_STATUS_NONE
      };
      const placeholderRect = (0, _utils.getTargetRect)(placeholderNodeRef.current);
      if (placeholderRect.top === 0 && placeholderRect.left === 0 && placeholderRect.width === 0 && placeholderRect.height === 0) {
        return;
      }
      const targetRect = (0, _utils.getTargetRect)(targetNode);
      const fixedTop = (0, _utils.getFixedTop)(placeholderRect, targetRect, internalOffsetTop);
      const fixedBottom = (0, _utils.getFixedBottom)(placeholderRect, targetRect, offsetBottom);
      if (fixedTop !== undefined) {
        newState.affixStyle = {
          position: 'fixed',
          top: fixedTop,
          width: placeholderRect.width,
          height: placeholderRect.height
        };
        newState.placeholderStyle = {
          width: placeholderRect.width,
          height: placeholderRect.height
        };
      } else if (fixedBottom !== undefined) {
        newState.affixStyle = {
          position: 'fixed',
          bottom: fixedBottom,
          width: placeholderRect.width,
          height: placeholderRect.height
        };
        newState.placeholderStyle = {
          width: placeholderRect.width,
          height: placeholderRect.height
        };
      }
      newState.lastAffix = !!newState.affixStyle;
      if (lastAffix !== newState.lastAffix) {
        onChange === null || onChange === void 0 ? void 0 : onChange(newState.lastAffix);
      }
      status.current = newState.status;
      setAffixStyle(newState.affixStyle);
      setPlaceholderStyle(newState.placeholderStyle);
      setLastAffix(newState.lastAffix);
    }
  };
  const prepareMeasure = () => {
    status.current = AFFIX_STATUS_PREPARE;
    measure();
    if (process.env.NODE_ENV === 'test') {
      onTestUpdatePosition === null || onTestUpdatePosition === void 0 ? void 0 : onTestUpdatePosition();
    }
  };
  const updatePosition = (0, _throttleByAnimationFrame.default)(() => {
    prepareMeasure();
  });
  const lazyUpdatePosition = (0, _throttleByAnimationFrame.default)(() => {
    // Check position change before measure to make Safari smooth
    if (targetFunc && affixStyle) {
      const targetNode = targetFunc();
      if (targetNode && placeholderNodeRef.current) {
        const targetRect = (0, _utils.getTargetRect)(targetNode);
        const placeholderRect = (0, _utils.getTargetRect)(placeholderNodeRef.current);
        const fixedTop = (0, _utils.getFixedTop)(placeholderRect, targetRect, internalOffsetTop);
        const fixedBottom = (0, _utils.getFixedBottom)(placeholderRect, targetRect, offsetBottom);
        if (fixedTop !== undefined && affixStyle.top === fixedTop || fixedBottom !== undefined && affixStyle.bottom === fixedBottom) {
          return;
        }
      }
    }
    // Directly call prepare measure since it's already throttled.
    prepareMeasure();
  });
  const addListeners = () => {
    const listenerTarget = targetFunc === null || targetFunc === void 0 ? void 0 : targetFunc();
    if (!listenerTarget) {
      return;
    }
    TRIGGER_EVENTS.forEach(eventName => {
      var _a;
      if (prevListener.current) {
        (_a = prevTarget.current) === null || _a === void 0 ? void 0 : _a.removeEventListener(eventName, prevListener.current);
      }
      listenerTarget === null || listenerTarget === void 0 ? void 0 : listenerTarget.addEventListener(eventName, lazyUpdatePosition);
    });
    prevTarget.current = listenerTarget;
    prevListener.current = lazyUpdatePosition;
  };
  const removeListeners = () => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
    }
    const newTarget = targetFunc === null || targetFunc === void 0 ? void 0 : targetFunc();
    TRIGGER_EVENTS.forEach(eventName => {
      var _a;
      newTarget === null || newTarget === void 0 ? void 0 : newTarget.removeEventListener(eventName, lazyUpdatePosition);
      if (prevListener.current) {
        (_a = prevTarget.current) === null || _a === void 0 ? void 0 : _a.removeEventListener(eventName, prevListener.current);
      }
    });
    updatePosition.cancel();
    lazyUpdatePosition.cancel();
  };
  _react.default.useImperativeHandle(ref, () => ({
    updatePosition
  }));
  // mount & unmount
  _react.default.useEffect(() => {
    // [Legacy] Wait for parent component ref has its value.
    // We should use target as directly element instead of function which makes element check hard.
    timer.current = setTimeout(addListeners);
    return () => removeListeners();
  }, []);
  _react.default.useEffect(() => {
    addListeners();
    return () => removeListeners();
  }, [target, affixStyle, lastAffix, offsetTop, offsetBottom]);
  _react.default.useEffect(() => {
    updatePosition();
  }, [target, offsetTop, offsetBottom]);
  const [wrapCSSVar, hashId, cssVarCls] = (0, _style.default)(affixPrefixCls);
  const rootCls = (0, _classnames.default)(rootClassName, hashId, affixPrefixCls, cssVarCls);
  const mergedCls = (0, _classnames.default)({
    [rootCls]: affixStyle
  });
  return wrapCSSVar(/*#__PURE__*/_react.default.createElement(_rcResizeObserver.default, {
    onResize: updatePosition
  }, /*#__PURE__*/_react.default.createElement("div", Object.assign({
    style: style,
    className: className,
    ref: placeholderNodeRef
  }, restProps), affixStyle && /*#__PURE__*/_react.default.createElement("div", {
    style: placeholderStyle,
    "aria-hidden": "true"
  }), /*#__PURE__*/_react.default.createElement("div", {
    className: mergedCls,
    ref: fixedNodeRef,
    style: affixStyle
  }, /*#__PURE__*/_react.default.createElement(_rcResizeObserver.default, {
    onResize: updatePosition
  }, children)))));
});
if (process.env.NODE_ENV !== 'production') {
  Affix.displayName = 'Affix';
}
var _default = exports.default = Affix;