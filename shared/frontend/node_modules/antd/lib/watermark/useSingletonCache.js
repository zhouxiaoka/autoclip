"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = useSingletonCache;
var React = _interopRequireWildcard(require("react"));
var _isEqual = _interopRequireDefault(require("rc-util/lib/isEqual"));
/**
 * Singleton cache will only take latest `cacheParams` as key
 * and return the result for callback matching.
 */
function useSingletonCache() {
  const cacheRef = React.useRef([null, null]);
  const getCache = (cacheKeys, callback) => {
    const filteredKeys = cacheKeys.map(item => item instanceof HTMLElement || Number.isNaN(item) ? '' : item);
    if (!(0, _isEqual.default)(cacheRef.current[0], filteredKeys)) {
      cacheRef.current = [filteredKeys, callback()];
    }
    return cacheRef.current[1];
  };
  return getCache;
}