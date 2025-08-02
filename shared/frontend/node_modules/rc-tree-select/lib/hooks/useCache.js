"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var React = _interopRequireWildcard(require("react"));
/**
 * This function will try to call requestIdleCallback if available to save performance.
 * No need `getLabel` here since already fetch on `rawLabeledValue`.
 */
var _default = exports.default = function _default(values) {
  var cacheRef = React.useRef({
    valueLabels: new Map()
  });
  return React.useMemo(function () {
    var valueLabels = cacheRef.current.valueLabels;
    var valueLabelsCache = new Map();
    var filledValues = values.map(function (item) {
      var value = item.value,
        label = item.label;
      var mergedLabel = label !== null && label !== void 0 ? label : valueLabels.get(value);

      // Save in cache
      valueLabelsCache.set(value, mergedLabel);
      return (0, _objectSpread2.default)((0, _objectSpread2.default)({}, item), {}, {
        label: mergedLabel
      });
    });
    cacheRef.current.valueLabels = valueLabelsCache;
    return [filledValues];
  }, [values]);
};