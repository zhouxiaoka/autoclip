"use client";

var __rest = this && this.__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
import * as React from 'react';
import classNames from 'classnames';
import { debounce } from 'throttle-debounce';
import { devUseWarning } from '../_util/warning';
import { useComponentConfig } from '../config-provider/context';
import Indicator from './Indicator';
import useStyle from './style/index';
import usePercent from './usePercent';
const _SpinSizes = ['small', 'default', 'large'];
// Render indicator
let defaultIndicator;
function shouldDelay(spinning, delay) {
  return !!spinning && !!delay && !Number.isNaN(Number(delay));
}
const Spin = props => {
  var _a;
  const {
      prefixCls: customizePrefixCls,
      spinning: customSpinning = true,
      delay = 0,
      className,
      rootClassName,
      size = 'default',
      tip,
      wrapperClassName,
      style,
      children,
      fullscreen = false,
      indicator,
      percent
    } = props,
    restProps = __rest(props, ["prefixCls", "spinning", "delay", "className", "rootClassName", "size", "tip", "wrapperClassName", "style", "children", "fullscreen", "indicator", "percent"]);
  const {
    getPrefixCls,
    direction,
    className: contextClassName,
    style: contextStyle,
    indicator: contextIndicator
  } = useComponentConfig('spin');
  const prefixCls = getPrefixCls('spin', customizePrefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = useStyle(prefixCls);
  const [spinning, setSpinning] = React.useState(() => customSpinning && !shouldDelay(customSpinning, delay));
  const mergedPercent = usePercent(spinning, percent);
  React.useEffect(() => {
    if (customSpinning) {
      const showSpinning = debounce(delay, () => {
        setSpinning(true);
      });
      showSpinning();
      return () => {
        var _a;
        (_a = showSpinning === null || showSpinning === void 0 ? void 0 : showSpinning.cancel) === null || _a === void 0 ? void 0 : _a.call(showSpinning);
      };
    }
    setSpinning(false);
  }, [delay, customSpinning]);
  const isNestedPattern = React.useMemo(() => typeof children !== 'undefined' && !fullscreen, [children, fullscreen]);
  if (process.env.NODE_ENV !== 'production') {
    const warning = devUseWarning('Spin');
    process.env.NODE_ENV !== "production" ? warning(!tip || isNestedPattern || fullscreen, 'usage', '`tip` only work in nest or fullscreen pattern.') : void 0;
  }
  const spinClassName = classNames(prefixCls, contextClassName, {
    [`${prefixCls}-sm`]: size === 'small',
    [`${prefixCls}-lg`]: size === 'large',
    [`${prefixCls}-spinning`]: spinning,
    [`${prefixCls}-show-text`]: !!tip,
    [`${prefixCls}-rtl`]: direction === 'rtl'
  }, className, !fullscreen && rootClassName, hashId, cssVarCls);
  const containerClassName = classNames(`${prefixCls}-container`, {
    [`${prefixCls}-blur`]: spinning
  });
  const mergedIndicator = (_a = indicator !== null && indicator !== void 0 ? indicator : contextIndicator) !== null && _a !== void 0 ? _a : defaultIndicator;
  const mergedStyle = Object.assign(Object.assign({}, contextStyle), style);
  const spinElement = /*#__PURE__*/React.createElement("div", Object.assign({}, restProps, {
    style: mergedStyle,
    className: spinClassName,
    "aria-live": "polite",
    "aria-busy": spinning
  }), /*#__PURE__*/React.createElement(Indicator, {
    prefixCls: prefixCls,
    indicator: mergedIndicator,
    percent: mergedPercent
  }), tip && (isNestedPattern || fullscreen) ? (/*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-text`
  }, tip)) : null);
  if (isNestedPattern) {
    return wrapCSSVar(/*#__PURE__*/React.createElement("div", Object.assign({}, restProps, {
      className: classNames(`${prefixCls}-nested-loading`, wrapperClassName, hashId, cssVarCls)
    }), spinning && /*#__PURE__*/React.createElement("div", {
      key: "loading"
    }, spinElement), /*#__PURE__*/React.createElement("div", {
      className: containerClassName,
      key: "container"
    }, children)));
  }
  if (fullscreen) {
    return wrapCSSVar(/*#__PURE__*/React.createElement("div", {
      className: classNames(`${prefixCls}-fullscreen`, {
        [`${prefixCls}-fullscreen-show`]: spinning
      }, rootClassName, hashId, cssVarCls)
    }, spinElement));
  }
  return wrapCSSVar(spinElement);
};
Spin.setDefaultIndicator = indicator => {
  defaultIndicator = indicator;
};
if (process.env.NODE_ENV !== 'production') {
  Spin.displayName = 'Spin';
}
export default Spin;