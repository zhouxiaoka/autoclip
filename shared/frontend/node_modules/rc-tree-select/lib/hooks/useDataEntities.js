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
var _warning = _interopRequireDefault(require("rc-util/lib/warning"));
var _valueUtil = require("../utils/valueUtil");
var _default = exports.default = function _default(treeData, fieldNames) {
  return React.useMemo(function () {
    var collection = (0, _treeUtil.convertDataToEntities)(treeData, {
      fieldNames: fieldNames,
      initWrapper: function initWrapper(wrapper) {
        return (0, _objectSpread2.default)((0, _objectSpread2.default)({}, wrapper), {}, {
          valueEntities: new Map()
        });
      },
      processEntity: function processEntity(entity, wrapper) {
        var val = entity.node[fieldNames.value];

        // Check if exist same value
        if (process.env.NODE_ENV !== 'production') {
          var key = entity.node.key;
          (0, _warning.default)(!(0, _valueUtil.isNil)(val), 'TreeNode `value` is invalidate: undefined');
          (0, _warning.default)(!wrapper.valueEntities.has(val), "Same `value` exist in the tree: ".concat(val));
          (0, _warning.default)(!key || String(key) === String(val), "`key` or `value` with TreeNode must be the same or you can remove one of them. key: ".concat(key, ", value: ").concat(val, "."));
        }
        wrapper.valueEntities.set(val, entity);
      }
    });
    return collection;
  }, [treeData, fieldNames]);
};