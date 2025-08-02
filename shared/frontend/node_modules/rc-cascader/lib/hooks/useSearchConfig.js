"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = useSearchConfig;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _typeof2 = _interopRequireDefault(require("@babel/runtime/helpers/typeof"));
var _warning = _interopRequireDefault(require("rc-util/lib/warning"));
var React = _interopRequireWildcard(require("react"));
// Convert `showSearch` to unique config
function useSearchConfig(showSearch) {
  return React.useMemo(function () {
    if (!showSearch) {
      return [false, {}];
    }
    var searchConfig = {
      matchInputWidth: true,
      limit: 50
    };
    if (showSearch && (0, _typeof2.default)(showSearch) === 'object') {
      searchConfig = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, searchConfig), showSearch);
    }
    if (searchConfig.limit <= 0) {
      searchConfig.limit = false;
      if (process.env.NODE_ENV !== 'production') {
        (0, _warning.default)(false, "'limit' of showSearch should be positive number or false.");
      }
    }
    return [true, searchConfig];
  }, [showSearch]);
}