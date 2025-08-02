"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _typeof2 = _interopRequireDefault(require("@babel/runtime/helpers/typeof"));
var _warning = _interopRequireDefault(require("rc-util/lib/warning"));
var _valueUtil = require("./valueUtil");
function warningProps(props) {
  var searchPlaceholder = props.searchPlaceholder,
    treeCheckStrictly = props.treeCheckStrictly,
    treeCheckable = props.treeCheckable,
    labelInValue = props.labelInValue,
    value = props.value,
    multiple = props.multiple,
    showCheckedStrategy = props.showCheckedStrategy,
    maxCount = props.maxCount;
  (0, _warning.default)(!searchPlaceholder, '`searchPlaceholder` has been removed.');
  if (treeCheckStrictly && labelInValue === false) {
    (0, _warning.default)(false, '`treeCheckStrictly` will force set `labelInValue` to `true`.');
  }
  if (labelInValue || treeCheckStrictly) {
    (0, _warning.default)((0, _valueUtil.toArray)(value).every(function (val) {
      return val && (0, _typeof2.default)(val) === 'object' && 'value' in val;
    }), 'Invalid prop `value` supplied to `TreeSelect`. You should use { label: string, value: string | number } or [{ label: string, value: string | number }] instead.');
  }
  if (treeCheckStrictly || multiple || treeCheckable) {
    (0, _warning.default)(!value || Array.isArray(value), '`value` should be an array when `TreeSelect` is checkable or multiple.');
  } else {
    (0, _warning.default)(!Array.isArray(value), '`value` should not be array when `TreeSelect` is single mode.');
  }
  if (maxCount && (showCheckedStrategy === 'SHOW_ALL' && !treeCheckStrictly || showCheckedStrategy === 'SHOW_PARENT')) {
    (0, _warning.default)(false, '`maxCount` not work with `showCheckedStrategy=SHOW_ALL` (when `treeCheckStrictly=false`) or `showCheckedStrategy=SHOW_PARENT`.');
  }
}
var _default = exports.default = warningProps;