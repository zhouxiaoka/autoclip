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
var _toArray = _interopRequireDefault(require("rc-util/lib/Children/toArray"));
var _reactNode = require("../_util/reactNode");
var _warning = require("../_util/warning");
var _configProvider = require("../config-provider");
var _useCSSVarCls = _interopRequireDefault(require("../config-provider/hooks/useCSSVarCls"));
var _popover = _interopRequireDefault(require("../popover"));
var _Avatar = _interopRequireDefault(require("./Avatar"));
var _AvatarContext = _interopRequireDefault(require("./AvatarContext"));
var _style = _interopRequireDefault(require("./style"));
const AvatarContextProvider = props => {
  const {
    size,
    shape
  } = React.useContext(_AvatarContext.default);
  const avatarContextValue = React.useMemo(() => ({
    size: props.size || size,
    shape: props.shape || shape
  }), [props.size, props.shape, size, shape]);
  return /*#__PURE__*/React.createElement(_AvatarContext.default.Provider, {
    value: avatarContextValue
  }, props.children);
};
const AvatarGroup = props => {
  var _a, _b, _c, _d;
  const {
    getPrefixCls,
    direction
  } = React.useContext(_configProvider.ConfigContext);
  const {
    prefixCls: customizePrefixCls,
    className,
    rootClassName,
    style,
    maxCount,
    maxStyle,
    size,
    shape,
    maxPopoverPlacement,
    maxPopoverTrigger,
    children,
    max
  } = props;
  if (process.env.NODE_ENV !== 'production') {
    const warning = (0, _warning.devUseWarning)('Avatar.Group');
    [['maxCount', 'max={{ count: number }}'], ['maxStyle', 'max={{ style: CSSProperties }}'], ['maxPopoverPlacement', 'max={{ popover: PopoverProps }}'], ['maxPopoverTrigger', 'max={{ popover: PopoverProps }}']].forEach(([deprecatedName, newName]) => {
      warning.deprecated(!(deprecatedName in props), deprecatedName, newName);
    });
  }
  const prefixCls = getPrefixCls('avatar', customizePrefixCls);
  const groupPrefixCls = `${prefixCls}-group`;
  const rootCls = (0, _useCSSVarCls.default)(prefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = (0, _style.default)(prefixCls, rootCls);
  const cls = (0, _classnames.default)(groupPrefixCls, {
    [`${groupPrefixCls}-rtl`]: direction === 'rtl'
  }, cssVarCls, rootCls, className, rootClassName, hashId);
  const childrenWithProps = (0, _toArray.default)(children).map((child, index) => (0, _reactNode.cloneElement)(child, {
    // eslint-disable-next-line react/no-array-index-key
    key: `avatar-key-${index}`
  }));
  const mergeCount = (max === null || max === void 0 ? void 0 : max.count) || maxCount;
  const numOfChildren = childrenWithProps.length;
  if (mergeCount && mergeCount < numOfChildren) {
    const childrenShow = childrenWithProps.slice(0, mergeCount);
    const childrenHidden = childrenWithProps.slice(mergeCount, numOfChildren);
    const mergeStyle = (max === null || max === void 0 ? void 0 : max.style) || maxStyle;
    const mergePopoverTrigger = ((_a = max === null || max === void 0 ? void 0 : max.popover) === null || _a === void 0 ? void 0 : _a.trigger) || maxPopoverTrigger || 'hover';
    const mergePopoverPlacement = ((_b = max === null || max === void 0 ? void 0 : max.popover) === null || _b === void 0 ? void 0 : _b.placement) || maxPopoverPlacement || 'top';
    const mergeProps = Object.assign(Object.assign({
      content: childrenHidden
    }, max === null || max === void 0 ? void 0 : max.popover), {
      classNames: {
        root: (0, _classnames.default)(`${groupPrefixCls}-popover`, (_d = (_c = max === null || max === void 0 ? void 0 : max.popover) === null || _c === void 0 ? void 0 : _c.classNames) === null || _d === void 0 ? void 0 : _d.root)
      },
      placement: mergePopoverPlacement,
      trigger: mergePopoverTrigger
    });
    childrenShow.push(/*#__PURE__*/React.createElement(_popover.default, Object.assign({
      key: "avatar-popover-key",
      destroyOnHidden: true
    }, mergeProps), /*#__PURE__*/React.createElement(_Avatar.default, {
      style: mergeStyle
    }, `+${numOfChildren - mergeCount}`)));
    return wrapCSSVar(/*#__PURE__*/React.createElement(AvatarContextProvider, {
      shape: shape,
      size: size
    }, /*#__PURE__*/React.createElement("div", {
      className: cls,
      style: style
    }, childrenShow)));
  }
  return wrapCSSVar(/*#__PURE__*/React.createElement(AvatarContextProvider, {
    shape: shape,
    size: size
  }, /*#__PURE__*/React.createElement("div", {
    className: cls,
    style: style
  }, childrenWithProps)));
};
var _default = exports.default = AvatarGroup;