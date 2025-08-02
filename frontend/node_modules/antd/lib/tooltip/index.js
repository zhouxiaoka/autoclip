"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var React = _interopRequireWildcard(require("react"));
var _classnames = _interopRequireDefault(require("classnames"));
var _rcTooltip = _interopRequireDefault(require("rc-tooltip"));
var _useMergedState = _interopRequireDefault(require("rc-util/lib/hooks/useMergedState"));
var _ContextIsolator = _interopRequireDefault(require("../_util/ContextIsolator"));
var _useZIndex = require("../_util/hooks/useZIndex");
var _motion = require("../_util/motion");
var _placements = _interopRequireDefault(require("../_util/placements"));
var _reactNode = require("../_util/reactNode");
var _warning = require("../_util/warning");
var _zindexContext = _interopRequireDefault(require("../_util/zindexContext"));
var _context = require("../config-provider/context");
var _internal = require("../theme/internal");
var _PurePanel = _interopRequireDefault(require("./PurePanel"));
var _style = _interopRequireDefault(require("./style"));
var _util = require("./util");
var __rest = void 0 && (void 0).__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
const InternalTooltip = /*#__PURE__*/React.forwardRef((props, ref) => {
  var _a, _b;
  const {
      prefixCls: customizePrefixCls,
      openClassName,
      getTooltipContainer,
      color,
      overlayInnerStyle,
      children,
      afterOpenChange,
      afterVisibleChange,
      destroyTooltipOnHide,
      destroyOnHidden,
      arrow = true,
      title,
      overlay,
      builtinPlacements,
      arrowPointAtCenter = false,
      autoAdjustOverflow = true,
      motion,
      getPopupContainer,
      placement = 'top',
      mouseEnterDelay = 0.1,
      mouseLeaveDelay = 0.1,
      overlayStyle,
      rootClassName,
      overlayClassName,
      styles,
      classNames: tooltipClassNames
    } = props,
    restProps = __rest(props, ["prefixCls", "openClassName", "getTooltipContainer", "color", "overlayInnerStyle", "children", "afterOpenChange", "afterVisibleChange", "destroyTooltipOnHide", "destroyOnHidden", "arrow", "title", "overlay", "builtinPlacements", "arrowPointAtCenter", "autoAdjustOverflow", "motion", "getPopupContainer", "placement", "mouseEnterDelay", "mouseLeaveDelay", "overlayStyle", "rootClassName", "overlayClassName", "styles", "classNames"]);
  const mergedShowArrow = !!arrow;
  const [, token] = (0, _internal.useToken)();
  const {
    getPopupContainer: getContextPopupContainer,
    getPrefixCls,
    direction,
    className: contextClassName,
    style: contextStyle,
    classNames: contextClassNames,
    styles: contextStyles
  } = (0, _context.useComponentConfig)('tooltip');
  // ============================== Ref ===============================
  const warning = (0, _warning.devUseWarning)('Tooltip');
  const tooltipRef = React.useRef(null);
  const forceAlign = () => {
    var _a;
    (_a = tooltipRef.current) === null || _a === void 0 ? void 0 : _a.forceAlign();
  };
  React.useImperativeHandle(ref, () => {
    var _a, _b;
    return {
      forceAlign,
      forcePopupAlign: () => {
        warning.deprecated(false, 'forcePopupAlign', 'forceAlign');
        forceAlign();
      },
      nativeElement: (_a = tooltipRef.current) === null || _a === void 0 ? void 0 : _a.nativeElement,
      popupElement: (_b = tooltipRef.current) === null || _b === void 0 ? void 0 : _b.popupElement
    };
  });
  // ============================== Warn ==============================
  if (process.env.NODE_ENV !== 'production') {
    [['visible', 'open'], ['defaultVisible', 'defaultOpen'], ['onVisibleChange', 'onOpenChange'], ['afterVisibleChange', 'afterOpenChange'], ['destroyTooltipOnHide', 'destroyOnHidden'], ['arrowPointAtCenter', 'arrow={{ pointAtCenter: true }}'], ['overlayStyle', 'styles={{ root: {} }}'], ['overlayInnerStyle', 'styles={{ body: {} }}'], ['overlayClassName', 'classNames={{ root: "" }}']].forEach(([deprecatedName, newName]) => {
      warning.deprecated(!(deprecatedName in props), deprecatedName, newName);
    });
    process.env.NODE_ENV !== "production" ? warning(!destroyTooltipOnHide || typeof destroyTooltipOnHide === 'boolean', 'usage', '`destroyTooltipOnHide` no need config `keepParent` anymore. Please use `boolean` value directly.') : void 0;
    process.env.NODE_ENV !== "production" ? warning(!arrow || typeof arrow === 'boolean' || !('arrowPointAtCenter' in arrow), 'deprecated', '`arrowPointAtCenter` in `arrow` is deprecated. Please use `pointAtCenter` instead.') : void 0;
  }
  // ============================== Open ==============================
  const [open, setOpen] = (0, _useMergedState.default)(false, {
    value: (_a = props.open) !== null && _a !== void 0 ? _a : props.visible,
    defaultValue: (_b = props.defaultOpen) !== null && _b !== void 0 ? _b : props.defaultVisible
  });
  const noTitle = !title && !overlay && title !== 0; // overlay for old version compatibility
  const onOpenChange = vis => {
    var _a, _b;
    setOpen(noTitle ? false : vis);
    if (!noTitle) {
      (_a = props.onOpenChange) === null || _a === void 0 ? void 0 : _a.call(props, vis);
      (_b = props.onVisibleChange) === null || _b === void 0 ? void 0 : _b.call(props, vis);
    }
  };
  const tooltipPlacements = React.useMemo(() => {
    var _a, _b;
    let mergedArrowPointAtCenter = arrowPointAtCenter;
    if (typeof arrow === 'object') {
      mergedArrowPointAtCenter = (_b = (_a = arrow.pointAtCenter) !== null && _a !== void 0 ? _a : arrow.arrowPointAtCenter) !== null && _b !== void 0 ? _b : arrowPointAtCenter;
    }
    return builtinPlacements || (0, _placements.default)({
      arrowPointAtCenter: mergedArrowPointAtCenter,
      autoAdjustOverflow,
      arrowWidth: mergedShowArrow ? token.sizePopupArrow : 0,
      borderRadius: token.borderRadius,
      offset: token.marginXXS,
      visibleFirst: true
    });
  }, [arrowPointAtCenter, arrow, builtinPlacements, token]);
  const memoOverlay = React.useMemo(() => {
    if (title === 0) {
      return title;
    }
    return overlay || title || '';
  }, [overlay, title]);
  const memoOverlayWrapper = /*#__PURE__*/React.createElement(_ContextIsolator.default, {
    space: true
  }, typeof memoOverlay === 'function' ? memoOverlay() : memoOverlay);
  const prefixCls = getPrefixCls('tooltip', customizePrefixCls);
  const rootPrefixCls = getPrefixCls();
  const injectFromPopover = props['data-popover-inject'];
  let tempOpen = open;
  // Hide tooltip when there is no title
  if (!('open' in props) && !('visible' in props) && noTitle) {
    tempOpen = false;
  }
  // ============================= Render =============================
  const child = /*#__PURE__*/React.isValidElement(children) && !(0, _reactNode.isFragment)(children) ? children : /*#__PURE__*/React.createElement("span", null, children);
  const childProps = child.props;
  const childCls = !childProps.className || typeof childProps.className === 'string' ? (0, _classnames.default)(childProps.className, openClassName || `${prefixCls}-open`) : childProps.className;
  // Style
  const [wrapCSSVar, hashId, cssVarCls] = (0, _style.default)(prefixCls, !injectFromPopover);
  // Color
  const colorInfo = (0, _util.parseColor)(prefixCls, color);
  const arrowContentStyle = colorInfo.arrowStyle;
  const rootClassNames = (0, _classnames.default)(overlayClassName, {
    [`${prefixCls}-rtl`]: direction === 'rtl'
  }, colorInfo.className, rootClassName, hashId, cssVarCls, contextClassName, contextClassNames.root, tooltipClassNames === null || tooltipClassNames === void 0 ? void 0 : tooltipClassNames.root);
  const bodyClassNames = (0, _classnames.default)(contextClassNames.body, tooltipClassNames === null || tooltipClassNames === void 0 ? void 0 : tooltipClassNames.body);
  // ============================ zIndex ============================
  const [zIndex, contextZIndex] = (0, _useZIndex.useZIndex)('Tooltip', restProps.zIndex);
  const content = /*#__PURE__*/React.createElement(_rcTooltip.default, Object.assign({}, restProps, {
    zIndex: zIndex,
    showArrow: mergedShowArrow,
    placement: placement,
    mouseEnterDelay: mouseEnterDelay,
    mouseLeaveDelay: mouseLeaveDelay,
    prefixCls: prefixCls,
    classNames: {
      root: rootClassNames,
      body: bodyClassNames
    },
    styles: {
      root: Object.assign(Object.assign(Object.assign(Object.assign(Object.assign({}, arrowContentStyle), contextStyles.root), contextStyle), overlayStyle), styles === null || styles === void 0 ? void 0 : styles.root),
      body: Object.assign(Object.assign(Object.assign(Object.assign({}, contextStyles.body), overlayInnerStyle), styles === null || styles === void 0 ? void 0 : styles.body), colorInfo.overlayStyle)
    },
    getTooltipContainer: getPopupContainer || getTooltipContainer || getContextPopupContainer,
    ref: tooltipRef,
    builtinPlacements: tooltipPlacements,
    overlay: memoOverlayWrapper,
    visible: tempOpen,
    onVisibleChange: onOpenChange,
    afterVisibleChange: afterOpenChange !== null && afterOpenChange !== void 0 ? afterOpenChange : afterVisibleChange,
    arrowContent: /*#__PURE__*/React.createElement("span", {
      className: `${prefixCls}-arrow-content`
    }),
    motion: {
      motionName: (0, _motion.getTransitionName)(rootPrefixCls, 'zoom-big-fast', props.transitionName),
      motionDeadline: 1000
    },
    // TODO: In the future, destroyTooltipOnHide in rc-tooltip needs to be upgrade to destroyOnHidden
    destroyTooltipOnHide: destroyOnHidden !== null && destroyOnHidden !== void 0 ? destroyOnHidden : !!destroyTooltipOnHide
  }), tempOpen ? (0, _reactNode.cloneElement)(child, {
    className: childCls
  }) : child);
  return wrapCSSVar(/*#__PURE__*/React.createElement(_zindexContext.default.Provider, {
    value: contextZIndex
  }, content));
});
const Tooltip = InternalTooltip;
if (process.env.NODE_ENV !== 'production') {
  Tooltip.displayName = 'Tooltip';
}
Tooltip._InternalPanelDoNotUseOrYouWillBeFired = _PurePanel.default;
var _default = exports.default = Tooltip;