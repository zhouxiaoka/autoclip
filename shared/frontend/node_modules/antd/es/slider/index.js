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
import RcSlider from 'rc-slider';
import raf from "rc-util/es/raf";
import { devUseWarning } from '../_util/warning';
import DisabledContext from '../config-provider/DisabledContext';
import SliderInternalContext from './Context';
import SliderTooltip from './SliderTooltip';
import useStyle from './style';
import useRafLock from './useRafLock';
import { useComponentConfig } from '../config-provider/context';
function getTipFormatter(tipFormatter, legacyTipFormatter) {
  if (tipFormatter || tipFormatter === null) {
    return tipFormatter;
  }
  if (legacyTipFormatter || legacyTipFormatter === null) {
    return legacyTipFormatter;
  }
  return val => typeof val === 'number' ? val.toString() : '';
}
const Slider = /*#__PURE__*/React.forwardRef((props, ref) => {
  const {
      prefixCls: customizePrefixCls,
      range,
      className,
      rootClassName,
      style,
      disabled,
      // Deprecated Props
      tooltipPrefixCls: legacyTooltipPrefixCls,
      tipFormatter: legacyTipFormatter,
      tooltipVisible: legacyTooltipVisible,
      getTooltipPopupContainer: legacyGetTooltipPopupContainer,
      tooltipPlacement: legacyTooltipPlacement,
      tooltip = {},
      onChangeComplete,
      classNames: sliderClassNames,
      styles
    } = props,
    restProps = __rest(props, ["prefixCls", "range", "className", "rootClassName", "style", "disabled", "tooltipPrefixCls", "tipFormatter", "tooltipVisible", "getTooltipPopupContainer", "tooltipPlacement", "tooltip", "onChangeComplete", "classNames", "styles"]);
  const {
    vertical
  } = props;
  const {
    getPrefixCls,
    direction: contextDirection,
    className: contextClassName,
    style: contextStyle,
    classNames: contextClassNames,
    styles: contextStyles,
    getPopupContainer
  } = useComponentConfig('slider');
  const contextDisabled = React.useContext(DisabledContext);
  const mergedDisabled = disabled !== null && disabled !== void 0 ? disabled : contextDisabled;
  // ============================= Context ==============================
  const {
    handleRender: contextHandleRender,
    direction: internalContextDirection
  } = React.useContext(SliderInternalContext);
  const mergedDirection = internalContextDirection || contextDirection;
  const isRTL = mergedDirection === 'rtl';
  // =============================== Open ===============================
  const [hoverOpen, setHoverOpen] = useRafLock();
  const [focusOpen, setFocusOpen] = useRafLock();
  const tooltipProps = Object.assign({}, tooltip);
  const {
    open: tooltipOpen,
    placement: tooltipPlacement,
    getPopupContainer: getTooltipPopupContainer,
    prefixCls: customizeTooltipPrefixCls,
    formatter: tipFormatter
  } = tooltipProps;
  const lockOpen = tooltipOpen !== null && tooltipOpen !== void 0 ? tooltipOpen : legacyTooltipVisible;
  const activeOpen = (hoverOpen || focusOpen) && lockOpen !== false;
  const mergedTipFormatter = getTipFormatter(tipFormatter, legacyTipFormatter);
  // ============================= Change ==============================
  const [dragging, setDragging] = useRafLock();
  const onInternalChangeComplete = nextValues => {
    onChangeComplete === null || onChangeComplete === void 0 ? void 0 : onChangeComplete(nextValues);
    setDragging(false);
  };
  // ============================ Placement ============================
  const getTooltipPlacement = (placement, vert) => {
    if (placement) {
      return placement;
    }
    if (!vert) {
      return 'top';
    }
    return isRTL ? 'left' : 'right';
  };
  // ============================== Style ===============================
  const prefixCls = getPrefixCls('slider', customizePrefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = useStyle(prefixCls);
  const rootClassNames = classNames(className, contextClassName, contextClassNames.root, sliderClassNames === null || sliderClassNames === void 0 ? void 0 : sliderClassNames.root, rootClassName, {
    [`${prefixCls}-rtl`]: isRTL,
    [`${prefixCls}-lock`]: dragging
  }, hashId, cssVarCls);
  // make reverse default on rtl direction
  if (isRTL && !restProps.vertical) {
    restProps.reverse = !restProps.reverse;
  }
  // ============================= Warning ==============================
  // Warning for deprecated usage
  if (process.env.NODE_ENV !== 'production') {
    const warning = devUseWarning('Slider');
    [['tooltipPrefixCls', 'prefixCls'], ['getTooltipPopupContainer', 'getPopupContainer'], ['tipFormatter', 'formatter'], ['tooltipPlacement', 'placement'], ['tooltipVisible', 'open']].forEach(([deprecatedName, newName]) => {
      warning.deprecated(!(deprecatedName in props), deprecatedName, `tooltip.${newName}`);
    });
  }
  // ============================== Handle ==============================
  React.useEffect(() => {
    const onMouseUp = () => {
      // Delay for 1 frame to make the click to enable hide tooltip
      // even when the handle is focused
      raf(() => {
        setFocusOpen(false);
      }, 1);
    };
    document.addEventListener('mouseup', onMouseUp);
    return () => {
      document.removeEventListener('mouseup', onMouseUp);
    };
  }, []);
  const useActiveTooltipHandle = range && !lockOpen;
  const handleRender = contextHandleRender || ((node, info) => {
    const {
      index
    } = info;
    const nodeProps = node.props;
    function proxyEvent(eventName, event, triggerRestPropsEvent) {
      var _a, _b, _c, _d;
      if (triggerRestPropsEvent) {
        (_b = (_a = restProps)[eventName]) === null || _b === void 0 ? void 0 : _b.call(_a, event);
      }
      (_d = (_c = nodeProps)[eventName]) === null || _d === void 0 ? void 0 : _d.call(_c, event);
    }
    const passedProps = Object.assign(Object.assign({}, nodeProps), {
      onMouseEnter: e => {
        setHoverOpen(true);
        proxyEvent('onMouseEnter', e);
      },
      onMouseLeave: e => {
        setHoverOpen(false);
        proxyEvent('onMouseLeave', e);
      },
      onMouseDown: e => {
        setFocusOpen(true);
        setDragging(true);
        proxyEvent('onMouseDown', e);
      },
      onFocus: e => {
        var _a;
        setFocusOpen(true);
        (_a = restProps.onFocus) === null || _a === void 0 ? void 0 : _a.call(restProps, e);
        proxyEvent('onFocus', e, true);
      },
      onBlur: e => {
        var _a;
        setFocusOpen(false);
        (_a = restProps.onBlur) === null || _a === void 0 ? void 0 : _a.call(restProps, e);
        proxyEvent('onBlur', e, true);
      }
    });
    const cloneNode = /*#__PURE__*/React.cloneElement(node, passedProps);
    const open = (!!lockOpen || activeOpen) && mergedTipFormatter !== null;
    // Wrap on handle with Tooltip when is single mode or multiple with all show tooltip
    if (!useActiveTooltipHandle) {
      return /*#__PURE__*/React.createElement(SliderTooltip, Object.assign({}, tooltipProps, {
        prefixCls: getPrefixCls('tooltip', customizeTooltipPrefixCls !== null && customizeTooltipPrefixCls !== void 0 ? customizeTooltipPrefixCls : legacyTooltipPrefixCls),
        title: mergedTipFormatter ? mergedTipFormatter(info.value) : '',
        value: info.value,
        open: open,
        placement: getTooltipPlacement(tooltipPlacement !== null && tooltipPlacement !== void 0 ? tooltipPlacement : legacyTooltipPlacement, vertical),
        key: index,
        classNames: {
          root: `${prefixCls}-tooltip`
        },
        getPopupContainer: getTooltipPopupContainer || legacyGetTooltipPopupContainer || getPopupContainer
      }), cloneNode);
    }
    return cloneNode;
  });
  // ========================== Active Handle ===========================
  const activeHandleRender = useActiveTooltipHandle ? (handle, info) => {
    const cloneNode = /*#__PURE__*/React.cloneElement(handle, {
      style: Object.assign(Object.assign({}, handle.props.style), {
        visibility: 'hidden'
      })
    });
    return /*#__PURE__*/React.createElement(SliderTooltip, Object.assign({}, tooltipProps, {
      prefixCls: getPrefixCls('tooltip', customizeTooltipPrefixCls !== null && customizeTooltipPrefixCls !== void 0 ? customizeTooltipPrefixCls : legacyTooltipPrefixCls),
      title: mergedTipFormatter ? mergedTipFormatter(info.value) : '',
      open: mergedTipFormatter !== null && activeOpen,
      placement: getTooltipPlacement(tooltipPlacement !== null && tooltipPlacement !== void 0 ? tooltipPlacement : legacyTooltipPlacement, vertical),
      key: "tooltip",
      classNames: {
        root: `${prefixCls}-tooltip`
      },
      getPopupContainer: getTooltipPopupContainer || legacyGetTooltipPopupContainer || getPopupContainer,
      draggingDelete: info.draggingDelete
    }), cloneNode);
  } : undefined;
  // ============================== Render ==============================
  const rootStyle = Object.assign(Object.assign(Object.assign(Object.assign({}, contextStyles.root), contextStyle), styles === null || styles === void 0 ? void 0 : styles.root), style);
  const mergedTracks = Object.assign(Object.assign({}, contextStyles.tracks), styles === null || styles === void 0 ? void 0 : styles.tracks);
  const mergedTracksClassNames = classNames(contextClassNames.tracks, sliderClassNames === null || sliderClassNames === void 0 ? void 0 : sliderClassNames.tracks);
  return wrapCSSVar(
  /*#__PURE__*/
  // @ts-ignore
  React.createElement(RcSlider, Object.assign({}, restProps, {
    classNames: Object.assign({
      handle: classNames(contextClassNames.handle, sliderClassNames === null || sliderClassNames === void 0 ? void 0 : sliderClassNames.handle),
      rail: classNames(contextClassNames.rail, sliderClassNames === null || sliderClassNames === void 0 ? void 0 : sliderClassNames.rail),
      track: classNames(contextClassNames.track, sliderClassNames === null || sliderClassNames === void 0 ? void 0 : sliderClassNames.track)
    }, mergedTracksClassNames ? {
      tracks: mergedTracksClassNames
    } : {}),
    styles: Object.assign({
      handle: Object.assign(Object.assign({}, contextStyles.handle), styles === null || styles === void 0 ? void 0 : styles.handle),
      rail: Object.assign(Object.assign({}, contextStyles.rail), styles === null || styles === void 0 ? void 0 : styles.rail),
      track: Object.assign(Object.assign({}, contextStyles.track), styles === null || styles === void 0 ? void 0 : styles.track)
    }, Object.keys(mergedTracks).length ? {
      tracks: mergedTracks
    } : {}),
    step: restProps.step,
    range: range,
    className: rootClassNames,
    style: rootStyle,
    disabled: mergedDisabled,
    ref: ref,
    prefixCls: prefixCls,
    handleRender: handleRender,
    activeHandleRender: activeHandleRender,
    onChangeComplete: onInternalChangeComplete
  })));
});
if (process.env.NODE_ENV !== 'production') {
  Slider.displayName = 'Slider';
}
export default Slider;