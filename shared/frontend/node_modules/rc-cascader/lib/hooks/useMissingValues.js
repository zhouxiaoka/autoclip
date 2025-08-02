"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = useMissingValues;
var React = _interopRequireWildcard(require("react"));
var _treeUtil = require("../utils/treeUtil");
function useMissingValues(options, fieldNames) {
  return React.useCallback(function (rawValues) {
    var missingValues = [];
    var existsValues = [];
    rawValues.forEach(function (valueCell) {
      var pathOptions = (0, _treeUtil.toPathOptions)(valueCell, options, fieldNames);
      if (pathOptions.every(function (opt) {
        return opt.option;
      })) {
        existsValues.push(valueCell);
      } else {
        missingValues.push(valueCell);
      }
    });
    return [existsValues, missingValues];
  }, [options, fieldNames]);
}