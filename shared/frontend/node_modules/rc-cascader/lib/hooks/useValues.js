"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = useValues;
var _slicedToArray2 = _interopRequireDefault(require("@babel/runtime/helpers/slicedToArray"));
var _conductUtil = require("rc-tree/lib/utils/conductUtil");
var React = _interopRequireWildcard(require("react"));
var _commonUtil = require("../utils/commonUtil");
function useValues(multiple, rawValues, getPathKeyEntities, getValueByKeyPath, getMissingValues) {
  // Fill `rawValues` with checked conduction values
  return React.useMemo(function () {
    var _getMissingValues = getMissingValues(rawValues),
      _getMissingValues2 = (0, _slicedToArray2.default)(_getMissingValues, 2),
      existValues = _getMissingValues2[0],
      missingValues = _getMissingValues2[1];
    if (!multiple || !rawValues.length) {
      return [existValues, [], missingValues];
    }
    var keyPathValues = (0, _commonUtil.toPathKeys)(existValues);
    var keyPathEntities = getPathKeyEntities();
    var _conductCheck = (0, _conductUtil.conductCheck)(keyPathValues, true, keyPathEntities),
      checkedKeys = _conductCheck.checkedKeys,
      halfCheckedKeys = _conductCheck.halfCheckedKeys;

    // Convert key back to value cells
    return [getValueByKeyPath(checkedKeys), getValueByKeyPath(halfCheckedKeys), missingValues];
  }, [multiple, rawValues, getPathKeyEntities, getValueByKeyPath, getMissingValues]);
}