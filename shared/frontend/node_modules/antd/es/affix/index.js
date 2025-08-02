"use client";

var __rest = this && this.__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
import React from 'react';
import classNames from 'classnames';
import ResizeObserver from 'rc-resize-observer';
import throttleByAnimationFrame from '../_util/throttleByAnimationFrame';
import { ConfigContext } from '../config-provider';
import useStyle from './style';
import { getFixedBottom, getFixedTop, getTargetRect } from './utils';
const TRIGGER_EVENTS = ['resize', 'scroll', 'touchstart', 'touchmove', 'touchend', 'pageshow', 'load'];
function getDefaultTarget() {
  return typeof window !== 'undefined' ? window : null;
}
const AFFIX_STATUS_NONE = 0;
const AFFIX_STATUS_PREPARE = 1;
const Affix = /*#__PURE__*/React.forwardRef((props, ref) => {
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
  } = React.useContext(ConfigContext);
  const affixPrefixCls = getPrefixCls('affix', prefixCls);
  const [lastAffix, setLastAffix] = React.useState(false);
  const [affixStyle, setAffixStyle] = React.useState();
  const [placeholderStyle, setPlaceholderStyle] = React.useState();
  const status = React.useRef(AFFIX_STATUS_NONE);
  const prevTarget = React.useRef(null);
  const prevListener = React.useRef(null);
  const placeholderNodeRef = React.useRef(null);
  const fixedNodeRef = React.useRef(null);
  const timer = React.useRef(null);
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
      const placeholderRect = getTargetRect(placeholderNodeRef.current);
      if (placeholderRect.top === 0 && placeholderRect.left === 0 && placeholderRect.width === 0 && placeholderRect.height === 0) {
        return;
      }
      const targetRect = getTargetRect(targetNode);
      const fixedTop = getFixedTop(placeholderRect, targetRect, internalOffsetTop);
      const fixedBottom = getFixedBottom(placeholderRect, targetRect, offsetBottom);
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
  const updatePosition = throttleByAnimationFrame(() => {
    prepareMeasure();
  });
  const lazyUpdatePosition = throttleByAnimationFrame(() => {
    // Check position change before measure to make Safari smooth
    if (targetFunc && affixStyle) {
      const targetNode = targetFunc();
      if (targetNode && placeholderNodeRef.current) {
        const targetRect = getTargetRect(targetNode);
        const placeholderRect = getTargetRect(placeholderNodeRef.current);
        const fixedTop = getFixedTop(placeholderRect, targetRect, internalOffsetTop);
        const fixedBottom = getFixedBottom(placeholderRect, targetRect, offsetBottom);
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
  React.useImperativeHandle(ref, () => ({
    updatePosition
  }));
  // mount & unmount
  React.useEffect(() => {
    // [Legacy] Wait for parent component ref has its value.
    // We should use target as directly element instead of function which makes element check hard.
    timer.current = setTimeout(addListeners);
    return () => removeListeners();
  }, []);
  React.useEffect(() => {
    addListeners();
    return () => removeListeners();
  }, [target, affixStyle, lastAffix, offsetTop, offsetBottom]);
  React.useEffect(() => {
    updatePosition();
  }, [target, offsetTop, offsetBottom]);
  const [wrapCSSVar, hashId, cssVarCls] = useStyle(affixPrefixCls);
  const rootCls = classNames(rootClassName, hashId, affixPrefixCls, cssVarCls);
  const mergedCls = classNames({
    [rootCls]: affixStyle
  });
  return wrapCSSVar(/*#__PURE__*/React.createElement(ResizeObserver, {
    onResize: updatePosition
  }, /*#__PURE__*/React.createElement("div", Object.assign({
    style: style,
    className: className,
    ref: placeholderNodeRef
  }, restProps), affixStyle && /*#__PURE__*/React.createElement("div", {
    style: placeholderStyle,
    "aria-hidden": "true"
  }), /*#__PURE__*/React.createElement("div", {
    className: mergedCls,
    ref: fixedNodeRef,
    style: affixStyle
  }, /*#__PURE__*/React.createElement(ResizeObserver, {
    onResize: updatePosition
  }, children)))));
});
if (process.env.NODE_ENV !== 'production') {
  Affix.displayName = 'Affix';
}
export default Affix;