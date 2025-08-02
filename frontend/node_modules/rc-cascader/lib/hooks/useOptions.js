"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = useOptions;
var React = _interopRequireWildcard(require("react"));
var _useEntities = _interopRequireDefault(require("./useEntities"));
function useOptions(mergedFieldNames, options) {
  var mergedOptions = React.useMemo(function () {
    return options || [];
  }, [options]);

  // Only used in multiple mode, this fn will not call in single mode
  var getPathKeyEntities = (0, _useEntities.default)(mergedOptions, mergedFieldNames);

  /** Convert path key back to value format */
  var getValueByKeyPath = React.useCallback(function (pathKeys) {
    var keyPathEntities = getPathKeyEntities();
    return pathKeys.map(function (pathKey) {
      var nodes = keyPathEntities[pathKey].nodes;
      return nodes.map(function (node) {
        return node[mergedFieldNames.value];
      });
    });
  }, [getPathKeyEntities, mergedFieldNames]);
  return [mergedOptions, getPathKeyEntities, getValueByKeyPath];
}