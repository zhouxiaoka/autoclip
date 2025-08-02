import _defineProperty from "@babel/runtime/helpers/esm/defineProperty";
import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import * as React from 'react';
import { fillLegacyProps } from "../utils/legacyUtil";
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
        var isMatch = keepAll || filterOptionFunc(searchValue, fillLegacyProps(node));
        var filteredChildren = filterTreeNodes(children || [], isMatch);
        if (isMatch || filteredChildren.length) {
          filtered.push(_objectSpread(_objectSpread({}, node), {}, _defineProperty({
            isLeaf: undefined
          }, fieldChildren, filteredChildren)));
        }
        return filtered;
      }, []);
    };
    return filterTreeNodes(treeData);
  }, [treeData, searchValue, fieldChildren, treeNodeFilterProp, filterTreeNode]);
};
export default useFilterTreeData;