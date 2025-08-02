"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = usePresets;
var _slicedToArray2 = _interopRequireDefault(require("@babel/runtime/helpers/slicedToArray"));
var React = _interopRequireWildcard(require("react"));
var _warning = _interopRequireDefault(require("rc-util/lib/warning"));
function usePresets(presets, legacyRanges) {
  return React.useMemo(function () {
    if (presets) {
      return presets;
    }
    if (legacyRanges) {
      (0, _warning.default)(false, '`ranges` is deprecated. Please use `presets` instead.');
      return Object.entries(legacyRanges).map(function (_ref) {
        var _ref2 = (0, _slicedToArray2.default)(_ref, 2),
          label = _ref2[0],
          value = _ref2[1];
        return {
          label: label,
          value: value
        };
      });
    }
    return [];
  }, [presets, legacyRanges]);
}