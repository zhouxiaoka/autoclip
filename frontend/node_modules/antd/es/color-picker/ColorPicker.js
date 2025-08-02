"use client";

var __rest = this && this.__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
import React, { useContext, useMemo } from 'react';
import classNames from 'classnames';
import useMergedState from "rc-util/es/hooks/useMergedState";
import ContextIsolator from '../_util/ContextIsolator';
import genPurePanel from '../_util/PurePanel';
import { getStatusClassNames } from '../_util/statusUtils';
import { devUseWarning } from '../_util/warning';
import { ConfigContext } from '../config-provider/context';
import DisabledContext from '../config-provider/DisabledContext';
import useCSSVarCls from '../config-provider/hooks/useCSSVarCls';
import useSize from '../config-provider/hooks/useSize';
import { FormItemInputContext } from '../form/context';
import Popover from '../popover';
import { useCompactItemContext } from '../space/Compact';
import { AggregationColor } from './color';
import ColorPickerPanel from './ColorPickerPanel';
import ColorTrigger from './components/ColorTrigger';
import useModeColor from './hooks/useModeColor';
import useStyle from './style';
import { genAlphaColor, generateColor, getColorAlpha } from './util';
const ColorPicker = props => {
  const {
      mode,
      value,
      defaultValue,
      format,
      defaultFormat,
      allowClear = false,
      presets,
      children,
      trigger = 'click',
      open,
      disabled,
      placement = 'bottomLeft',
      arrow = true,
      panelRender,
      showText,
      style,
      className,
      size: customizeSize,
      rootClassName,
      prefixCls: customizePrefixCls,
      styles,
      disabledAlpha = false,
      onFormatChange,
      onChange,
      onClear,
      onOpenChange,
      onChangeComplete,
      getPopupContainer,
      autoAdjustOverflow = true,
      destroyTooltipOnHide,
      destroyOnHidden,
      disabledFormat
    } = props,
    rest = __rest(props, ["mode", "value", "defaultValue", "format", "defaultFormat", "allowClear", "presets", "children", "trigger", "open", "disabled", "placement", "arrow", "panelRender", "showText", "style", "className", "size", "rootClassName", "prefixCls", "styles", "disabledAlpha", "onFormatChange", "onChange", "onClear", "onOpenChange", "onChangeComplete", "getPopupContainer", "autoAdjustOverflow", "destroyTooltipOnHide", "destroyOnHidden", "disabledFormat"]);
  const {
    getPrefixCls,
    direction,
    colorPicker
  } = useContext(ConfigContext);
  const contextDisabled = useContext(DisabledContext);
  const mergedDisabled = disabled !== null && disabled !== void 0 ? disabled : contextDisabled;
  const [popupOpen, setPopupOpen] = useMergedState(false, {
    value: open,
    postState: openData => !mergedDisabled && openData,
    onChange: onOpenChange
  });
  const [formatValue, setFormatValue] = useMergedState(format, {
    value: format,
    defaultValue: defaultFormat,
    onChange: onFormatChange
  });
  const prefixCls = getPrefixCls('color-picker', customizePrefixCls);
  // ================== Value & Mode =================
  const [mergedColor, setColor, modeState, setModeState, modeOptions] = useModeColor(defaultValue, value, mode);
  const isAlphaColor = useMemo(() => getColorAlpha(mergedColor) < 100, [mergedColor]);
  // ==================== Change =====================
  // To enhance user experience, we cache the gradient color when switch from gradient to single
  // If user not modify single color, we will use the cached gradient color.
  const [cachedGradientColor, setCachedGradientColor] = React.useState(null);
  const onInternalChangeComplete = color => {
    if (onChangeComplete) {
      let changeColor = generateColor(color);
      // ignore alpha color
      if (disabledAlpha && isAlphaColor) {
        changeColor = genAlphaColor(color);
      }
      onChangeComplete(changeColor);
    }
  };
  const onInternalChange = (data, changeFromPickerDrag) => {
    let color = generateColor(data);
    // ignore alpha color
    if (disabledAlpha && isAlphaColor) {
      color = genAlphaColor(color);
    }
    setColor(color);
    setCachedGradientColor(null);
    // Trigger change event
    if (onChange) {
      onChange(color, color.toCssString());
    }
    // Only for drag-and-drop color picking
    if (!changeFromPickerDrag) {
      onInternalChangeComplete(color);
    }
  };
  // =================== Gradient ====================
  const [activeIndex, setActiveIndex] = React.useState(0);
  const [gradientDragging, setGradientDragging] = React.useState(false);
  // Mode change should also trigger color change
  const onInternalModeChange = newMode => {
    setModeState(newMode);
    if (newMode === 'single' && mergedColor.isGradient()) {
      setActiveIndex(0);
      onInternalChange(new AggregationColor(mergedColor.getColors()[0].color));
      // Should after `onInternalChange` since it will clear the cached color
      setCachedGradientColor(mergedColor);
    } else if (newMode === 'gradient' && !mergedColor.isGradient()) {
      const baseColor = isAlphaColor ? genAlphaColor(mergedColor) : mergedColor;
      onInternalChange(new AggregationColor(cachedGradientColor || [{
        percent: 0,
        color: baseColor
      }, {
        percent: 100,
        color: baseColor
      }]));
    }
  };
  // ================== Form Status ==================
  const {
    status: contextStatus
  } = React.useContext(FormItemInputContext);
  // ==================== Compact ====================
  const {
    compactSize,
    compactItemClassnames
  } = useCompactItemContext(prefixCls, direction);
  // ===================== Style =====================
  const mergedSize = useSize(ctx => {
    var _a;
    return (_a = customizeSize !== null && customizeSize !== void 0 ? customizeSize : compactSize) !== null && _a !== void 0 ? _a : ctx;
  });
  const rootCls = useCSSVarCls(prefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = useStyle(prefixCls, rootCls);
  const rtlCls = {
    [`${prefixCls}-rtl`]: direction
  };
  const mergedRootCls = classNames(rootClassName, cssVarCls, rootCls, rtlCls);
  const mergedCls = classNames(getStatusClassNames(prefixCls, contextStatus), {
    [`${prefixCls}-sm`]: mergedSize === 'small',
    [`${prefixCls}-lg`]: mergedSize === 'large'
  }, compactItemClassnames, colorPicker === null || colorPicker === void 0 ? void 0 : colorPicker.className, mergedRootCls, className, hashId);
  const mergedPopupCls = classNames(prefixCls, mergedRootCls);
  // ===================== Warning ======================
  if (process.env.NODE_ENV !== 'production') {
    const warning = devUseWarning('ColorPicker');
    process.env.NODE_ENV !== "production" ? warning(!(disabledAlpha && isAlphaColor), 'usage', '`disabledAlpha` will make the alpha to be 100% when use alpha color.') : void 0;
  }
  const popoverProps = {
    open: popupOpen,
    trigger,
    placement,
    arrow,
    rootClassName,
    getPopupContainer,
    autoAdjustOverflow,
    destroyOnHidden: destroyOnHidden !== null && destroyOnHidden !== void 0 ? destroyOnHidden : !!destroyTooltipOnHide
  };
  const mergedStyle = Object.assign(Object.assign({}, colorPicker === null || colorPicker === void 0 ? void 0 : colorPicker.style), style);
  // ============================ zIndex ============================
  return wrapCSSVar(/*#__PURE__*/React.createElement(Popover, Object.assign({
    style: styles === null || styles === void 0 ? void 0 : styles.popup,
    styles: {
      body: styles === null || styles === void 0 ? void 0 : styles.popupOverlayInner
    },
    onOpenChange: visible => {
      if (!visible || !mergedDisabled) {
        setPopupOpen(visible);
      }
    },
    content: /*#__PURE__*/React.createElement(ContextIsolator, {
      form: true
    }, /*#__PURE__*/React.createElement(ColorPickerPanel, {
      mode: modeState,
      onModeChange: onInternalModeChange,
      modeOptions: modeOptions,
      prefixCls: prefixCls,
      value: mergedColor,
      allowClear: allowClear,
      disabled: mergedDisabled,
      disabledAlpha: disabledAlpha,
      presets: presets,
      panelRender: panelRender,
      format: formatValue,
      onFormatChange: setFormatValue,
      onChange: onInternalChange,
      onChangeComplete: onInternalChangeComplete,
      onClear: onClear,
      activeIndex: activeIndex,
      onActive: setActiveIndex,
      gradientDragging: gradientDragging,
      onGradientDragging: setGradientDragging,
      disabledFormat: disabledFormat
    })),
    classNames: {
      root: mergedPopupCls
    }
  }, popoverProps), children || (/*#__PURE__*/React.createElement(ColorTrigger, Object.assign({
    activeIndex: popupOpen ? activeIndex : -1,
    open: popupOpen,
    className: mergedCls,
    style: mergedStyle,
    prefixCls: prefixCls,
    disabled: mergedDisabled,
    showText: showText,
    format: formatValue
  }, rest, {
    color: mergedColor
  })))));
};
if (process.env.NODE_ENV !== 'production') {
  ColorPicker.displayName = 'ColorPicker';
}
const PurePanel = genPurePanel(ColorPicker, undefined, props => Object.assign(Object.assign({}, props), {
  placement: 'bottom',
  autoAdjustOverflow: false
}), 'color-picker', /* istanbul ignore next */
prefixCls => prefixCls);
ColorPicker._InternalPanelDoNotUseOrYouWillBeFired = PurePanel;
export default ColorPicker;