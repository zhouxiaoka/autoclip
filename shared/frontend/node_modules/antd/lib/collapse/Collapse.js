"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var React = _interopRequireWildcard(require("react"));
var _RightOutlined = _interopRequireDefault(require("@ant-design/icons/RightOutlined"));
var _classnames = _interopRequireDefault(require("classnames"));
var _rcCollapse = _interopRequireDefault(require("rc-collapse"));
var _toArray = _interopRequireDefault(require("rc-util/lib/Children/toArray"));
var _omit = _interopRequireDefault(require("rc-util/lib/omit"));
var _motion = _interopRequireDefault(require("../_util/motion"));
var _reactNode = require("../_util/reactNode");
var _warning = require("../_util/warning");
var _context = require("../config-provider/context");
var _useSize = _interopRequireDefault(require("../config-provider/hooks/useSize"));
var _CollapsePanel = _interopRequireDefault(require("./CollapsePanel"));
var _style = _interopRequireDefault(require("./style"));
const Collapse = /*#__PURE__*/React.forwardRef((props, ref) => {
  const {
    getPrefixCls,
    direction,
    expandIcon: contextExpandIcon,
    className: contextClassName,
    style: contextStyle
  } = (0, _context.useComponentConfig)('collapse');
  const {
    prefixCls: customizePrefixCls,
    className,
    rootClassName,
    style,
    bordered = true,
    ghost,
    size: customizeSize,
    expandIconPosition = 'start',
    children,
    destroyInactivePanel,
    destroyOnHidden,
    expandIcon
  } = props;
  const mergedSize = (0, _useSize.default)(ctx => {
    var _a;
    return (_a = customizeSize !== null && customizeSize !== void 0 ? customizeSize : ctx) !== null && _a !== void 0 ? _a : 'middle';
  });
  const prefixCls = getPrefixCls('collapse', customizePrefixCls);
  const rootPrefixCls = getPrefixCls();
  const [wrapCSSVar, hashId, cssVarCls] = (0, _style.default)(prefixCls);
  if (process.env.NODE_ENV !== 'production') {
    const warning = (0, _warning.devUseWarning)('Collapse');
    // Warning if use legacy type `expandIconPosition`
    process.env.NODE_ENV !== "production" ? warning(expandIconPosition !== 'left' && expandIconPosition !== 'right', 'deprecated', '`expandIconPosition` with `left` or `right` is deprecated. Please use `start` or `end` instead.') : void 0;
    warning.deprecated(!('destroyInactivePanel' in props), 'destroyInactivePanel', 'destroyOnHidden');
  }
  // Align with logic position
  const mergedExpandIconPosition = React.useMemo(() => {
    if (expandIconPosition === 'left') {
      return 'start';
    }
    return expandIconPosition === 'right' ? 'end' : expandIconPosition;
  }, [expandIconPosition]);
  const mergedExpandIcon = expandIcon !== null && expandIcon !== void 0 ? expandIcon : contextExpandIcon;
  const renderExpandIcon = React.useCallback((panelProps = {}) => {
    const icon = typeof mergedExpandIcon === 'function' ? mergedExpandIcon(panelProps) : (/*#__PURE__*/React.createElement(_RightOutlined.default, {
      rotate: panelProps.isActive ? direction === 'rtl' ? -90 : 90 : undefined,
      "aria-label": panelProps.isActive ? 'expanded' : 'collapsed'
    }));
    return (0, _reactNode.cloneElement)(icon, () => {
      var _a;
      return {
        className: (0, _classnames.default)((_a = icon === null || icon === void 0 ? void 0 : icon.props) === null || _a === void 0 ? void 0 : _a.className, `${prefixCls}-arrow`)
      };
    });
  }, [mergedExpandIcon, prefixCls]);
  const collapseClassName = (0, _classnames.default)(`${prefixCls}-icon-position-${mergedExpandIconPosition}`, {
    [`${prefixCls}-borderless`]: !bordered,
    [`${prefixCls}-rtl`]: direction === 'rtl',
    [`${prefixCls}-ghost`]: !!ghost,
    [`${prefixCls}-${mergedSize}`]: mergedSize !== 'middle'
  }, contextClassName, className, rootClassName, hashId, cssVarCls);
  const openMotion = Object.assign(Object.assign({}, (0, _motion.default)(rootPrefixCls)), {
    motionAppear: false,
    leavedClassName: `${prefixCls}-content-hidden`
  });
  const items = React.useMemo(() => {
    if (children) {
      return (0, _toArray.default)(children).map((child, index) => {
        var _a, _b;
        const childProps = child.props;
        if (childProps === null || childProps === void 0 ? void 0 : childProps.disabled) {
          const key = (_a = child.key) !== null && _a !== void 0 ? _a : String(index);
          const mergedChildProps = Object.assign(Object.assign({}, (0, _omit.default)(child.props, ['disabled'])), {
            key,
            collapsible: (_b = childProps.collapsible) !== null && _b !== void 0 ? _b : 'disabled'
          });
          return (0, _reactNode.cloneElement)(child, mergedChildProps);
        }
        return child;
      });
    }
    return null;
  }, [children]);
  return wrapCSSVar(
  /*#__PURE__*/
  // @ts-ignore
  React.createElement(_rcCollapse.default, Object.assign({
    ref: ref,
    openMotion: openMotion
  }, (0, _omit.default)(props, ['rootClassName']), {
    expandIcon: renderExpandIcon,
    prefixCls: prefixCls,
    className: collapseClassName,
    style: Object.assign(Object.assign({}, contextStyle), style),
    // TODO: In the future, destroyInactivePanel in rc-collapse needs to be upgrade to destroyOnHidden
    destroyInactivePanel: destroyOnHidden !== null && destroyOnHidden !== void 0 ? destroyOnHidden : destroyInactivePanel
  }), items));
});
if (process.env.NODE_ENV !== 'production') {
  Collapse.displayName = 'Collapse';
}
var _default = exports.default = Object.assign(Collapse, {
  Panel: _CollapsePanel.default
});