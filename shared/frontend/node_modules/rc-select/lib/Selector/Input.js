"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");
var _typeof = require("@babel/runtime/helpers/typeof");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _objectWithoutProperties2 = _interopRequireDefault(require("@babel/runtime/helpers/objectWithoutProperties"));
var React = _interopRequireWildcard(require("react"));
var _classnames = _interopRequireDefault(require("classnames"));
var _ref = require("rc-util/lib/ref");
var _warning = require("rc-util/lib/warning");
var _composeProps = _interopRequireDefault(require("rc-util/lib/composeProps"));
var _excluded = ["prefixCls", "id", "inputElement", "autoFocus", "autoComplete", "editable", "activeDescendantId", "value", "open", "attrs"];
function _getRequireWildcardCache(e) { if ("function" != typeof WeakMap) return null; var r = new WeakMap(), t = new WeakMap(); return (_getRequireWildcardCache = function _getRequireWildcardCache(e) { return e ? t : r; })(e); }
function _interopRequireWildcard(e, r) { if (!r && e && e.__esModule) return e; if (null === e || "object" != _typeof(e) && "function" != typeof e) return { default: e }; var t = _getRequireWildcardCache(r); if (t && t.has(e)) return t.get(e); var n = { __proto__: null }, a = Object.defineProperty && Object.getOwnPropertyDescriptor; for (var u in e) if ("default" !== u && Object.prototype.hasOwnProperty.call(e, u)) { var i = a ? Object.getOwnPropertyDescriptor(e, u) : null; i && (i.get || i.set) ? Object.defineProperty(n, u, i) : n[u] = e[u]; } return n.default = e, t && t.set(e, n), n; }
var Input = function Input(props, ref) {
  var prefixCls = props.prefixCls,
    id = props.id,
    inputElement = props.inputElement,
    autoFocus = props.autoFocus,
    autoComplete = props.autoComplete,
    editable = props.editable,
    activeDescendantId = props.activeDescendantId,
    value = props.value,
    open = props.open,
    attrs = props.attrs,
    restProps = (0, _objectWithoutProperties2.default)(props, _excluded);
  var inputNode = inputElement || /*#__PURE__*/React.createElement("input", null);
  var _inputNode = inputNode,
    originRef = _inputNode.ref,
    originProps = _inputNode.props;
  (0, _warning.warning)(!('maxLength' in inputNode.props), "Passing 'maxLength' to input element directly may not work because input in BaseSelect is controlled.");
  inputNode = /*#__PURE__*/React.cloneElement(inputNode, (0, _objectSpread2.default)((0, _objectSpread2.default)((0, _objectSpread2.default)({
    type: 'search'
  }, (0, _composeProps.default)(restProps, originProps, true)), {}, {
    // Override over origin props
    id: id,
    ref: (0, _ref.composeRef)(ref, originRef),
    autoComplete: autoComplete || 'off',
    autoFocus: autoFocus,
    className: (0, _classnames.default)("".concat(prefixCls, "-selection-search-input"), originProps === null || originProps === void 0 ? void 0 : originProps.className),
    role: 'combobox',
    'aria-expanded': open || false,
    'aria-haspopup': 'listbox',
    'aria-owns': "".concat(id, "_list"),
    'aria-autocomplete': 'list',
    'aria-controls': "".concat(id, "_list"),
    'aria-activedescendant': open ? activeDescendantId : undefined
  }, attrs), {}, {
    value: editable ? value : '',
    readOnly: !editable,
    unselectable: !editable ? 'on' : null,
    style: (0, _objectSpread2.default)((0, _objectSpread2.default)({}, originProps.style), {}, {
      opacity: editable ? null : 0
    })
  }));
  return inputNode;
};
var RefInput = /*#__PURE__*/React.forwardRef(Input);
if (process.env.NODE_ENV !== 'production') {
  RefInput.displayName = 'Input';
}
var _default = exports.default = RefInput;