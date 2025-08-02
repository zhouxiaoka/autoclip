"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var React = _interopRequireWildcard(require("react"));
var _treeUtil = require("rc-tree/lib/utils/treeUtil");
var _commonUtil = require("../utils/commonUtil");
/** Lazy parse options data into conduct-able info to avoid perf issue in single mode */
var _default = exports.default = function _default(options, fieldNames) {
  var cacheRef = React.useRef({
    options: [],
    info: {
      keyEntities: {},
      pathKeyEntities: {}
    }
  });
  var getEntities = React.useCallback(function () {
    if (cacheRef.current.options !== options) {
      cacheRef.current.options = options;
      cacheRef.current.info = (0, _treeUtil.convertDataToEntities)(options, {
        fieldNames: fieldNames,
        initWrapper: function initWrapper(wrapper) {
          return (0, _objectSpread2.default)((0, _objectSpread2.default)({}, wrapper), {}, {
            pathKeyEntities: {}
          });
        },
        processEntity: function processEntity(entity, wrapper) {
          var pathKey = entity.nodes.map(function (node) {
            return node[fieldNames.value];
          }).join(_commonUtil.VALUE_SPLIT);
          wrapper.pathKeyEntities[pathKey] = entity;

          // Overwrite origin key.
          // this is very hack but we need let conduct logic work with connect path
          entity.key = pathKey;
        }
      });
    }
    return cacheRef.current.info.pathKeyEntities;
  }, [fieldNames, options]);
  return getEntities;
};