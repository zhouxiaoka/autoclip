"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");
var _typeof3 = require("@babel/runtime/helpers/typeof");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var _defineProperty2 = _interopRequireDefault(require("@babel/runtime/helpers/defineProperty"));
var _typeof2 = _interopRequireDefault(require("@babel/runtime/helpers/typeof"));
var _classnames = _interopRequireDefault(require("classnames"));
var _react = _interopRequireWildcard(require("react"));
var _commonUtils = require("./utils/commonUtils");
function _getRequireWildcardCache(e) { if ("function" != typeof WeakMap) return null; var r = new WeakMap(), t = new WeakMap(); return (_getRequireWildcardCache = function _getRequireWildcardCache(e) { return e ? t : r; })(e); }
function _interopRequireWildcard(e, r) { if (!r && e && e.__esModule) return e; if (null === e || "object" != _typeof3(e) && "function" != typeof e) return { default: e }; var t = _getRequireWildcardCache(r); if (t && t.has(e)) return t.get(e); var n = { __proto__: null }, a = Object.defineProperty && Object.getOwnPropertyDescriptor; for (var u in e) if ("default" !== u && Object.prototype.hasOwnProperty.call(e, u)) { var i = a ? Object.getOwnPropertyDescriptor(e, u) : null; i && (i.get || i.set) ? Object.defineProperty(n, u, i) : n[u] = e[u]; } return n.default = e, t && t.set(e, n), n; }
var BaseInput = /*#__PURE__*/_react.default.forwardRef(function (props, ref) {
  var _props, _props2, _props3;
  var inputEl = props.inputElement,
    children = props.children,
    prefixCls = props.prefixCls,
    prefix = props.prefix,
    suffix = props.suffix,
    addonBefore = props.addonBefore,
    addonAfter = props.addonAfter,
    className = props.className,
    style = props.style,
    disabled = props.disabled,
    readOnly = props.readOnly,
    focused = props.focused,
    triggerFocus = props.triggerFocus,
    allowClear = props.allowClear,
    value = props.value,
    handleReset = props.handleReset,
    hidden = props.hidden,
    classes = props.classes,
    classNames = props.classNames,
    dataAttrs = props.dataAttrs,
    styles = props.styles,
    components = props.components,
    onClear = props.onClear;
  var inputElement = children !== null && children !== void 0 ? children : inputEl;
  var AffixWrapperComponent = (components === null || components === void 0 ? void 0 : components.affixWrapper) || 'span';
  var GroupWrapperComponent = (components === null || components === void 0 ? void 0 : components.groupWrapper) || 'span';
  var WrapperComponent = (components === null || components === void 0 ? void 0 : components.wrapper) || 'span';
  var GroupAddonComponent = (components === null || components === void 0 ? void 0 : components.groupAddon) || 'span';
  var containerRef = (0, _react.useRef)(null);
  var onInputClick = function onInputClick(e) {
    var _containerRef$current;
    if ((_containerRef$current = containerRef.current) !== null && _containerRef$current !== void 0 && _containerRef$current.contains(e.target)) {
      triggerFocus === null || triggerFocus === void 0 || triggerFocus();
    }
  };
  var hasAffix = (0, _commonUtils.hasPrefixSuffix)(props);
  var element = /*#__PURE__*/(0, _react.cloneElement)(inputElement, {
    value: value,
    className: (0, _classnames.default)((_props = inputElement.props) === null || _props === void 0 ? void 0 : _props.className, !hasAffix && (classNames === null || classNames === void 0 ? void 0 : classNames.variant)) || null
  });

  // ======================== Ref ======================== //
  var groupRef = (0, _react.useRef)(null);
  _react.default.useImperativeHandle(ref, function () {
    return {
      nativeElement: groupRef.current || containerRef.current
    };
  });

  // ================== Prefix & Suffix ================== //
  if (hasAffix) {
    // ================== Clear Icon ================== //
    var clearIcon = null;
    if (allowClear) {
      var needClear = !disabled && !readOnly && value;
      var clearIconCls = "".concat(prefixCls, "-clear-icon");
      var iconNode = (0, _typeof2.default)(allowClear) === 'object' && allowClear !== null && allowClear !== void 0 && allowClear.clearIcon ? allowClear.clearIcon : '✖';
      clearIcon = /*#__PURE__*/_react.default.createElement("button", {
        type: "button",
        tabIndex: -1,
        onClick: function onClick(event) {
          handleReset === null || handleReset === void 0 || handleReset(event);
          onClear === null || onClear === void 0 || onClear();
        }
        // Do not trigger onBlur when clear input
        // https://github.com/ant-design/ant-design/issues/31200
        ,
        onMouseDown: function onMouseDown(e) {
          return e.preventDefault();
        },
        className: (0, _classnames.default)(clearIconCls, (0, _defineProperty2.default)((0, _defineProperty2.default)({}, "".concat(clearIconCls, "-hidden"), !needClear), "".concat(clearIconCls, "-has-suffix"), !!suffix))
      }, iconNode);
    }
    var affixWrapperPrefixCls = "".concat(prefixCls, "-affix-wrapper");
    var affixWrapperCls = (0, _classnames.default)(affixWrapperPrefixCls, (0, _defineProperty2.default)((0, _defineProperty2.default)((0, _defineProperty2.default)((0, _defineProperty2.default)((0, _defineProperty2.default)({}, "".concat(prefixCls, "-disabled"), disabled), "".concat(affixWrapperPrefixCls, "-disabled"), disabled), "".concat(affixWrapperPrefixCls, "-focused"), focused), "".concat(affixWrapperPrefixCls, "-readonly"), readOnly), "".concat(affixWrapperPrefixCls, "-input-with-clear-btn"), suffix && allowClear && value), classes === null || classes === void 0 ? void 0 : classes.affixWrapper, classNames === null || classNames === void 0 ? void 0 : classNames.affixWrapper, classNames === null || classNames === void 0 ? void 0 : classNames.variant);
    var suffixNode = (suffix || allowClear) && /*#__PURE__*/_react.default.createElement("span", {
      className: (0, _classnames.default)("".concat(prefixCls, "-suffix"), classNames === null || classNames === void 0 ? void 0 : classNames.suffix),
      style: styles === null || styles === void 0 ? void 0 : styles.suffix
    }, clearIcon, suffix);
    element = /*#__PURE__*/_react.default.createElement(AffixWrapperComponent, (0, _extends2.default)({
      className: affixWrapperCls,
      style: styles === null || styles === void 0 ? void 0 : styles.affixWrapper,
      onClick: onInputClick
    }, dataAttrs === null || dataAttrs === void 0 ? void 0 : dataAttrs.affixWrapper, {
      ref: containerRef
    }), prefix && /*#__PURE__*/_react.default.createElement("span", {
      className: (0, _classnames.default)("".concat(prefixCls, "-prefix"), classNames === null || classNames === void 0 ? void 0 : classNames.prefix),
      style: styles === null || styles === void 0 ? void 0 : styles.prefix
    }, prefix), element, suffixNode);
  }

  // ================== Addon ================== //
  if ((0, _commonUtils.hasAddon)(props)) {
    var wrapperCls = "".concat(prefixCls, "-group");
    var addonCls = "".concat(wrapperCls, "-addon");
    var groupWrapperCls = "".concat(wrapperCls, "-wrapper");
    var mergedWrapperClassName = (0, _classnames.default)("".concat(prefixCls, "-wrapper"), wrapperCls, classes === null || classes === void 0 ? void 0 : classes.wrapper, classNames === null || classNames === void 0 ? void 0 : classNames.wrapper);
    var mergedGroupClassName = (0, _classnames.default)(groupWrapperCls, (0, _defineProperty2.default)({}, "".concat(groupWrapperCls, "-disabled"), disabled), classes === null || classes === void 0 ? void 0 : classes.group, classNames === null || classNames === void 0 ? void 0 : classNames.groupWrapper);

    // Need another wrapper for changing display:table to display:inline-block
    // and put style prop in wrapper
    element = /*#__PURE__*/_react.default.createElement(GroupWrapperComponent, {
      className: mergedGroupClassName,
      ref: groupRef
    }, /*#__PURE__*/_react.default.createElement(WrapperComponent, {
      className: mergedWrapperClassName
    }, addonBefore && /*#__PURE__*/_react.default.createElement(GroupAddonComponent, {
      className: addonCls
    }, addonBefore), element, addonAfter && /*#__PURE__*/_react.default.createElement(GroupAddonComponent, {
      className: addonCls
    }, addonAfter)));
  }

  // `className` and `style` are always on the root element
  return /*#__PURE__*/_react.default.cloneElement(element, {
    className: (0, _classnames.default)((_props2 = element.props) === null || _props2 === void 0 ? void 0 : _props2.className, className) || null,
    style: (0, _objectSpread2.default)((0, _objectSpread2.default)({}, (_props3 = element.props) === null || _props3 === void 0 ? void 0 : _props3.style), style),
    hidden: hidden
  });
});
var _default = exports.default = BaseInput;