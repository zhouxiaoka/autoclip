"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var React = _interopRequireWildcard(require("react"));
var _ExclamationCircleFilled = _interopRequireDefault(require("@ant-design/icons/ExclamationCircleFilled"));
var _classnames = _interopRequireDefault(require("classnames"));
var _useMergedState = _interopRequireDefault(require("rc-util/lib/hooks/useMergedState"));
var _omit = _interopRequireDefault(require("rc-util/lib/omit"));
var _context = require("../config-provider/context");
var _popover = _interopRequireDefault(require("../popover"));
var _PurePanel = _interopRequireWildcard(require("./PurePanel"));
var _style = _interopRequireDefault(require("./style"));
var __rest = void 0 && (void 0).__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
const InternalPopconfirm = /*#__PURE__*/React.forwardRef((props, ref) => {
  var _a, _b;
  const {
      prefixCls: customizePrefixCls,
      placement = 'top',
      trigger = 'click',
      okType = 'primary',
      icon = /*#__PURE__*/React.createElement(_ExclamationCircleFilled.default, null),
      children,
      overlayClassName,
      onOpenChange,
      onVisibleChange,
      overlayStyle,
      styles,
      classNames: popconfirmClassNames
    } = props,
    restProps = __rest(props, ["prefixCls", "placement", "trigger", "okType", "icon", "children", "overlayClassName", "onOpenChange", "onVisibleChange", "overlayStyle", "styles", "classNames"]);
  const {
    getPrefixCls,
    className: contextClassName,
    style: contextStyle,
    classNames: contextClassNames,
    styles: contextStyles
  } = (0, _context.useComponentConfig)('popconfirm');
  const [open, setOpen] = (0, _useMergedState.default)(false, {
    value: (_a = props.open) !== null && _a !== void 0 ? _a : props.visible,
    defaultValue: (_b = props.defaultOpen) !== null && _b !== void 0 ? _b : props.defaultVisible
  });
  const settingOpen = (value, e) => {
    setOpen(value, true);
    onVisibleChange === null || onVisibleChange === void 0 ? void 0 : onVisibleChange(value);
    onOpenChange === null || onOpenChange === void 0 ? void 0 : onOpenChange(value, e);
  };
  const close = e => {
    settingOpen(false, e);
  };
  const onConfirm = e => {
    var _a;
    return (_a = props.onConfirm) === null || _a === void 0 ? void 0 : _a.call(void 0, e);
  };
  const onCancel = e => {
    var _a;
    settingOpen(false, e);
    (_a = props.onCancel) === null || _a === void 0 ? void 0 : _a.call(void 0, e);
  };
  const onInternalOpenChange = (value, e) => {
    const {
      disabled = false
    } = props;
    if (disabled) {
      return;
    }
    settingOpen(value, e);
  };
  const prefixCls = getPrefixCls('popconfirm', customizePrefixCls);
  const rootClassNames = (0, _classnames.default)(prefixCls, contextClassName, overlayClassName, contextClassNames.root, popconfirmClassNames === null || popconfirmClassNames === void 0 ? void 0 : popconfirmClassNames.root);
  const bodyClassNames = (0, _classnames.default)(contextClassNames.body, popconfirmClassNames === null || popconfirmClassNames === void 0 ? void 0 : popconfirmClassNames.body);
  const [wrapCSSVar] = (0, _style.default)(prefixCls);
  return wrapCSSVar(/*#__PURE__*/React.createElement(_popover.default, Object.assign({}, (0, _omit.default)(restProps, ['title']), {
    trigger: trigger,
    placement: placement,
    onOpenChange: onInternalOpenChange,
    open: open,
    ref: ref,
    classNames: {
      root: rootClassNames,
      body: bodyClassNames
    },
    styles: {
      root: Object.assign(Object.assign(Object.assign(Object.assign({}, contextStyles.root), contextStyle), overlayStyle), styles === null || styles === void 0 ? void 0 : styles.root),
      body: Object.assign(Object.assign({}, contextStyles.body), styles === null || styles === void 0 ? void 0 : styles.body)
    },
    content: /*#__PURE__*/React.createElement(_PurePanel.Overlay, Object.assign({
      okType: okType,
      icon: icon
    }, props, {
      prefixCls: prefixCls,
      close: close,
      onConfirm: onConfirm,
      onCancel: onCancel
    })),
    "data-popover-inject": true
  }), children));
});
const Popconfirm = InternalPopconfirm;
// We don't care debug panel
/* istanbul ignore next */
Popconfirm._InternalPanelDoNotUseOrYouWillBeFired = _PurePanel.default;
if (process.env.NODE_ENV !== 'production') {
  Popconfirm.displayName = 'Popconfirm';
}
var _default = exports.default = Popconfirm;