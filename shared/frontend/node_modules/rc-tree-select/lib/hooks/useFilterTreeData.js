"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _defineProperty2 = _interopRequireDefault(require("@babel/runtime/helpers/defineProperty"));
var _objectSpread3 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var React = _interopRequireWildcard(require("react"));
var _legacyUtil = require("../utils/legacyUtil");
var useFilterTreeData = function useFilterTreeData(treeData, searchValue, options) {
  var fieldNames = options.fieldNames,
    treeNodeFilterProp = options.treeNodeFilterProp,
    filterTreeNode = options.filterTreeNode;
  var fieldChildren = fieldNames.children;
  return React.useMemo(function () {
    if (!searchValue || filterTreeNode === false) {
      return treeData;
    }
    var filterOptionFunc = typeof filterTreeNode === 'function' ? filterTreeNode : function (_, dataNode) {
      return String(dataNode[treeNodeFilterProp]).toUpperCase().includes(searchValue.toUpperCase());
    };
    var filterTreeNodes = function filterTreeNodes(nodes) {
      var keepAll = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : false;
      return nodes.reduce(function (filtered, node) {
        var children = node[fieldChildren];
        var isMatch = keepAll || filterOptionFunc(searchValue, (0, _legacyUtil.fillLegacyProps)(node));
        var filteredChildren = filterTreeNodes(children || [], isMatch);
        if (isMatch || filteredChildren.length) {
          filtered.push((0, _objectSpread3.default)((0, _objectSpread3.default)({}, node), {}, (0, _defineProperty2.default)({
            isLeaf: undefined
          }, fieldChildren, filteredChildren)));
        }
        return filtered;
      }, []);
    };
    return filterTreeNodes(treeData);
  }, [treeData, searchValue, fieldChildren, treeNodeFilterProp, filterTreeNode]);
};
var _default = exports.default = useFilterTreeData;