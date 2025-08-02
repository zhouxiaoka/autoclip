import _toConsumableArray from "@babel/runtime/helpers/esm/toConsumableArray";
import * as React from 'react';
import { conductCheck } from "rc-tree/es/utils/conductUtil";
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
      var conductResult = conductCheck(checkedKeys, true, keyEntities);
      finalCheckedKeys = conductResult.checkedKeys;
      finalHalfCheckedKeys = conductResult.halfCheckedKeys;
    }
    return [Array.from(new Set([].concat(_toConsumableArray(missingValues), _toConsumableArray(finalCheckedKeys)))), finalHalfCheckedKeys];
  }, [rawLabeledValues, rawHalfCheckedValues, treeConduction, keyEntities]);
};
export default useCheckedKeys;