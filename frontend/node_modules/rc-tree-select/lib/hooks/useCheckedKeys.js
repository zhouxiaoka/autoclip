"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _toConsumableArray2 = _interopRequireDefault(require("@babel/runtime/helpers/toConsumableArray"));
var React = _interopRequireWildcard(require("react"));
var _conductUtil = require("rc-tree/lib/utils/conductUtil");
var useCheckedKeys = function useCheckedKeys(rawLabeledValues, rawHalfCheckedValues, treeConduction, keyEntities) {
  return React.useMemo(function () {
    var extractValues = function extractValues(values) {
      return values.map(function (_ref) {
        var value = _ref.value;
        return value;
      });
    };
    var checkedKeys = extractValues(rawLabeledValues);
    var halfCheckedKeys = extractValues(rawHalfCheckedValues);
    var missingValues = checkedKeys.filter(function (key) {
      return !keyEntities[key];
    });
    var finalCheckedKeys = checkedKeys;
    var finalHalfCheckedKeys = halfCheckedKeys;
    if (treeConduction) {
      var conductResult = (0, _conductUtil.conductCheck)(checkedKeys, true, keyEntities);
      finalCheckedKeys = conductResult.checkedKeys;
      finalHalfCheckedKeys = conductResult.halfCheckedKeys;
    }
    return [Array.from(new Set([].concat((0, _toConsumableArray2.default)(missingValues), (0, _toConsumableArray2.default)(finalCheckedKeys)))), finalHalfCheckedKeys];
  }, [rawLabeledValues, rawHalfCheckedValues, treeConduction, keyEntities]);
};
var _default = exports.default = useCheckedKeys;