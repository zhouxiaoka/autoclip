import _typeof from "@babel/runtime/helpers/esm/typeof";
import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import * as React from 'react';
import { convertChildrenToData } from "../utils/legacyUtil";
function buildTreeStructure(nodes, config) {
  var id = config.id,
    pId = config.pId,
    rootPId = config.rootPId;
  var nodeMap = new Map();
  var rootNodes = [];
  nodes.forEach(function (node) {
    var nodeKey = node[id];
    var clonedNode = _objectSpread(_objectSpread({}, node), {}, {
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
export default function useTreeData(treeData, children, simpleMode) {
  return React.useMemo(function () {
    if (treeData) {
      if (simpleMode) {
        var config = _objectSpread({
          id: 'id',
          pId: 'pId',
          rootPId: null
        }, _typeof(simpleMode) === 'object' ? simpleMode : {});
        return buildTreeStructure(treeData, config);
      }
      return treeData;
    }
    return convertChildrenToData(children);
  }, [children, simpleMode, treeData]);
}