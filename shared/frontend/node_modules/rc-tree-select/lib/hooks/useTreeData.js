"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = useTreeData;
var _typeof2 = _interopRequireDefault(require("@babel/runtime/helpers/typeof"));
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var React = _interopRequireWildcard(require("react"));
var _legacyUtil = require("../utils/legacyUtil");
function buildTreeStructure(nodes, config) {
  var id = config.id,
    pId = config.pId,
    rootPId = config.rootPId;
  var nodeMap = new Map();
  var rootNodes = [];
  nodes.forEach(function (node) {
    var nodeKey = node[id];
    var clonedNode = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, node), {}, {
      key: node.key || nodeKey
    });
    nodeMap.set(nodeKey, clonedNode);
  });
  nodeMap.forEach(function (node) {
    var parentKey = node[pId];
    var parent = nodeMap.get(parentKey);
    if (parent) {
      parent.children = parent.children || [];
      parent.children.push(node);
    } else if (parentKey === rootPId || rootPId === null) {
      rootNodes.push(node);
    }
  });
  return rootNodes;
}

/**
 * 将 `treeData` 或 `children` 转换为格式化的 `treeData`。
 * 如果 `treeData` 或 `children` 没有变化，则不会重新计算。
 */
function useTreeData(treeData, children, simpleMode) {
  return React.useMemo(function () {
    if (treeData) {
      if (simpleMode) {
        var config = (0, _objectSpread2.default)({
          id: 'id',
          pId: 'pId',
          rootPId: null
        }, (0, _typeof2.default)(simpleMode) === 'object' ? simpleMode : {});
        return buildTreeStructure(treeData, config);
      }
      return treeData;
    }
    return (0, _legacyUtil.convertChildrenToData)(children);
  }, [children, simpleMode, treeData]);
}