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
var _omit = _interopRequireDefault(require("rc-util/lib/omit"));
var _colors = require("../_util/colors");
var _useClosable = _interopRequireWildcard(require("../_util/hooks/useClosable"));
var _reactNode = require("../_util/reactNode");
var _warning = require("../_util/warning");
var _wave = _interopRequireDefault(require("../_util/wave"));
var _configProvider = require("../config-provider");
var _CheckableTag = _interopRequireDefault(require("./CheckableTag"));
var _style = _interopRequireDefault(require("./style"));
var _presetCmp = _interopRequireDefault(require("./style/presetCmp"));
var _statusCmp = _interopRequireDefault(require("./style/statusCmp"));
var __rest = void 0 && (void 0).__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
const InternalTag = /*#__PURE__*/React.forwardRef((tagProps, ref) => {
  const {
      prefixCls: customizePrefixCls,
      className,
      rootClassName,
      style,
      children,
      icon,
      color,
      onClose,
      bordered = true,
      visible: deprecatedVisible
    } = tagProps,
    props = __rest(tagProps, ["prefixCls", "className", "rootClassName", "style", "children", "icon", "color", "onClose", "bordered", "visible"]);
  const {
    getPrefixCls,
    direction,
    tag: tagContext
  } = React.useContext(_configProvider.ConfigContext);
  const [visible, setVisible] = React.useState(true);
  const domProps = (0, _omit.default)(props, ['closeIcon', 'closable']);
  // Warning for deprecated usage
  if (process.env.NODE_ENV !== 'production') {
    const warning = (0, _warning.devUseWarning)('Tag');
    warning.deprecated(!('visible' in tagProps), 'visible', 'visible && <Tag />');
  }
  React.useEffect(() => {
    if (deprecatedVisible !== undefined) {
      setVisible(deprecatedVisible);
    }
  }, [deprecatedVisible]);
  const isPreset = (0, _colors.isPresetColor)(color);
  const isStatus = (0, _colors.isPresetStatusColor)(color);
  const isInternalColor = isPreset || isStatus;
  const tagStyle = Object.assign(Object.assign({
    backgroundColor: color && !isInternalColor ? color : undefined
  }, tagContext === null || tagContext === void 0 ? void 0 : tagContext.style), style);
  const prefixCls = getPrefixCls('tag', customizePrefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = (0, _style.default)(prefixCls);
  // Style
  const tagClassName = (0, _classnames.default)(prefixCls, tagContext === null || tagContext === void 0 ? void 0 : tagContext.className, {
    [`${prefixCls}-${color}`]: isInternalColor,
    [`${prefixCls}-has-color`]: color && !isInternalColor,
    [`${prefixCls}-hidden`]: !visible,
    [`${prefixCls}-rtl`]: direction === 'rtl',
    [`${prefixCls}-borderless`]: !bordered
  }, className, rootClassName, hashId, cssVarCls);
  const handleCloseClick = e => {
    e.stopPropagation();
    onClose === null || onClose === void 0 ? void 0 : onClose(e);
    if (e.defaultPrevented) {
      return;
    }
    setVisible(false);
  };
  const [, mergedCloseIcon] = (0, _useClosable.default)((0, _useClosable.pickClosable)(tagProps), (0, _useClosable.pickClosable)(tagContext), {
    closable: false,
    closeIconRender: iconNode => {
      const replacement = /*#__PURE__*/React.createElement("span", {
        className: `${prefixCls}-close-icon`,
        onClick: handleCloseClick
      }, iconNode);
      return (0, _reactNode.replaceElement)(iconNode, replacement, originProps => ({
        onClick: e => {
          var _a;
          (_a = originProps === null || originProps === void 0 ? void 0 : originProps.onClick) === null || _a === void 0 ? void 0 : _a.call(originProps, e);
          handleCloseClick(e);
        },
        className: (0, _classnames.default)(originProps === null || originProps === void 0 ? void 0 : originProps.className, `${prefixCls}-close-icon`)
      }));
    }
  });
  const isNeedWave = typeof props.onClick === 'function' || children && children.type === 'a';
  const iconNode = icon || null;
  const kids = iconNode ? (/*#__PURE__*/React.createElement(React.Fragment, null, iconNode, children && /*#__PURE__*/React.createElement("span", null, children))) : children;
  const tagNode = /*#__PURE__*/React.createElement("span", Object.assign({}, domProps, {
    ref: ref,
    className: tagClassName,
    style: tagStyle
  }), kids, mergedCloseIcon, isPreset && /*#__PURE__*/React.createElement(_presetCmp.default, {
    key: "preset",
    prefixCls: prefixCls
  }), isStatus && /*#__PURE__*/React.createElement(_statusCmp.default, {
    key: "status",
    prefixCls: prefixCls
  }));
  return wrapCSSVar(isNeedWave ? /*#__PURE__*/React.createElement(_wave.default, {
    component: "Tag"
  }, tagNode) : tagNode);
});
const Tag = InternalTag;
if (process.env.NODE_ENV !== 'production') {
  Tag.displayName = 'Tag';
}
Tag.CheckableTag = _CheckableTag.default;
var _default = exports.default = Tag;