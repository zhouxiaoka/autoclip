import _extends from "@babel/runtime/helpers/esm/extends";
import _createForOfIteratorHelper from "@babel/runtime/helpers/esm/createForOfIteratorHelper";
import _toConsumableArray from "@babel/runtime/helpers/esm/toConsumableArray";
import _slicedToArray from "@babel/runtime/helpers/esm/slicedToArray";
import { useBaseProps } from 'rc-select';
import Tree from 'rc-tree';
import { UnstableContext } from 'rc-tree';
import KeyCode from "rc-util/es/KeyCode";
import useMemo from "rc-util/es/hooks/useMemo";
import * as React from 'react';
import LegacyContext from "./LegacyContext";
import TreeSelectContext from "./TreeSelectContext";
import { getAllKeys, isCheckDisabled } from "./utils/valueUtil";
import { useEvent } from 'rc-util';
var HIDDEN_STYLE = {
  width: 0,
  height: 0,
  display: 'flex',
  overflow: 'hidden',
  opacity: 0,
  border: 0,
  padding: 0,
  margin: 0
};
var OptionList = function OptionList(_, ref) {
  var _useBaseProps = useBaseProps(),
    prefixCls = _useBaseProps.prefixCls,
    multiple = _useBaseProps.multiple,
    searchValue = _useBaseProps.searchValue,
    toggleOpen = _useBaseProps.toggleOpen,
    open = _useBaseProps.open,
    notFoundContent = _useBaseProps.notFoundContent;
  var _React$useContext = React.useContext(TreeSelectContext),
    virtual = _React$useContext.virtual,
    listHeight = _React$useContext.listHeight,
    listItemHeight = _React$useContext.listItemHeight,
    listItemScrollOffset = _React$useContext.listItemScrollOffset,
    treeData = _React$useContext.treeData,
    fieldNames = _React$useContext.fieldNames,
    onSelect = _React$useContext.onSelect,
    dropdownMatchSelectWidth = _React$useContext.dropdownMatchSelectWidth,
    treeExpandAction = _React$useContext.treeExpandAction,
    treeTitleRender = _React$useContext.treeTitleRender,
    onPopupScroll = _React$useContext.onPopupScroll,
    leftMaxCount = _React$useContext.leftMaxCount,
    leafCountOnly = _React$useContext.leafCountOnly,
    valueEntities = _React$useContext.valueEntities;
  var _React$useContext2 = React.useContext(LegacyContext),
    checkable = _React$useContext2.checkable,
    checkedKeys = _React$useContext2.checkedKeys,
    halfCheckedKeys = _React$useContext2.halfCheckedKeys,
    treeExpandedKeys = _React$useContext2.treeExpandedKeys,
    treeDefaultExpandAll = _React$useContext2.treeDefaultExpandAll,
    treeDefaultExpandedKeys = _React$useContext2.treeDefaultExpandedKeys,
    onTreeExpand = _React$useContext2.onTreeExpand,
    treeIcon = _React$useContext2.treeIcon,
    showTreeIcon = _React$useContext2.showTreeIcon,
    switcherIcon = _React$useContext2.switcherIcon,
    treeLine = _React$useContext2.treeLine,
    treeNodeFilterProp = _React$useContext2.treeNodeFilterProp,
    loadData = _React$useContext2.loadData,
    treeLoadedKeys = _React$useContext2.treeLoadedKeys,
    treeMotion = _React$useContext2.treeMotion,
    onTreeLoad = _React$useContext2.onTreeLoad,
    keyEntities = _React$useContext2.keyEntities;
  var treeRef = React.useRef();
  var memoTreeData = useMemo(function () {
    return treeData;
  },
  // eslint-disable-next-line react-hooks/exhaustive-deps
  [open, treeData], function (prev, next) {
    return next[0] && prev[1] !== next[1];
  });

  // ========================== Values ==========================
  var mergedCheckedKeys = React.useMemo(function () {
    if (!checkable) {
      return null;
    }
    return {
      checked: checkedKeys,
      halfChecked: halfCheckedKeys
    };
  }, [checkable, checkedKeys, halfCheckedKeys]);

  // ========================== Scroll ==========================
  React.useEffect(function () {
    // Single mode should scroll to current key
    if (open && !multiple && checkedKeys.length) {
      var _treeRef$current;
      (_treeRef$current = treeRef.current) === null || _treeRef$current === void 0 || _treeRef$current.scrollTo({
        key: checkedKeys[0]
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // ========================== Events ==========================
  var onListMouseDown = function onListMouseDown(event) {
    event.preventDefault();
  };
  var onInternalSelect = function onInternalSelect(__, info) {
    var node = info.node;
    if (checkable && isCheckDisabled(node)) {
      return;
    }
    onSelect(node.key, {
      selected: !checkedKeys.includes(node.key)
    });
    if (!multiple) {
      toggleOpen(false);
    }
  };

  // =========================== Keys ===========================
  var _React$useState = React.useState(treeDefaultExpandedKeys),
    _React$useState2 = _slicedToArray(_React$useState, 2),
    expandedKeys = _React$useState2[0],
    setExpandedKeys = _React$useState2[1];
  var _React$useState3 = React.useState(null),
    _React$useState4 = _slicedToArray(_React$useState3, 2),
    searchExpandedKeys = _React$useState4[0],
    setSearchExpandedKeys = _React$useState4[1];
  var mergedExpandedKeys = React.useMemo(function () {
    if (treeExpandedKeys) {
      return _toConsumableArray(treeExpandedKeys);
    }
    return searchValue ? searchExpandedKeys : expandedKeys;
  }, [expandedKeys, searchExpandedKeys, treeExpandedKeys, searchValue]);
  var onInternalExpand = function onInternalExpand(keys) {
    setExpandedKeys(keys);
    setSearchExpandedKeys(keys);
    if (onTreeExpand) {
      onTreeExpand(keys);
    }
  };

  // ========================== Search ==========================
  var lowerSearchValue = String(searchValue).toLowerCase();
  var filterTreeNode = function filterTreeNode(treeNode) {
    if (!lowerSearchValue) {
      return false;
    }
    return String(treeNode[treeNodeFilterProp]).toLowerCase().includes(lowerSearchValue);
  };
  React.useEffect(function () {
    if (searchValue) {
      setSearchExpandedKeys(getAllKeys(treeData, fieldNames));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchValue]);

  // ========================= Disabled =========================
  // Cache disabled states in React state to ensure re-render when cache updates
  var _React$useState5 = React.useState(function () {
      return new Map();
    }),
    _React$useState6 = _slicedToArray(_React$useState5, 2),
    disabledCache = _React$useState6[0],
    setDisabledCache = _React$useState6[1];
  React.useEffect(function () {
    if (leftMaxCount) {
      setDisabledCache(new Map());
    }
  }, [leftMaxCount]);
  function getDisabledWithCache(node) {
    var value = node[fieldNames.value];
    if (!disabledCache.has(value)) {
      var entity = valueEntities.get(value);
      var isLeaf = (entity.children || []).length === 0;
      if (!isLeaf) {
        var checkableChildren = entity.children.filter(function (childTreeNode) {
          return !childTreeNode.node.disabled && !childTreeNode.node.disableCheckbox && !checkedKeys.includes(childTreeNode.node[fieldNames.value]);
        });
        var checkableChildrenCount = checkableChildren.length;
        disabledCache.set(value, checkableChildrenCount > leftMaxCount);
      } else {
        disabledCache.set(value, false);
      }
    }
    return disabledCache.get(value);
  }
  var nodeDisabled = useEvent(function (node) {
    var nodeValue = node[fieldNames.value];
    if (checkedKeys.includes(nodeValue)) {
      return false;
    }
    if (leftMaxCount === null) {
      return false;
    }
    if (leftMaxCount <= 0) {
      return true;
    }

    // This is a low performance calculation
    if (leafCountOnly && leftMaxCount) {
      return getDisabledWithCache(node);
    }
    return false;
  });

  // ========================== Get First Selectable Node ==========================
  var getFirstMatchingNode = function getFirstMatchingNode(nodes) {
    var _iterator = _createForOfIteratorHelper(nodes),
      _step;
    try {
      for (_iterator.s(); !(_step = _iterator.n()).done;) {
        var node = _step.value;
        if (node.disabled || node.selectable === false) {
          continue;
        }
        if (searchValue) {
          if (filterTreeNode(node)) {
            return node;
          }
        } else {
          return node;
        }
        if (node[fieldNames.children]) {
          var matchInChildren = getFirstMatchingNode(node[fieldNames.children]);
          if (matchInChildren) {
            return matchInChildren;
          }
        }
      }
    } catch (err) {
      _iterator.e(err);
    } finally {
      _iterator.f();
    }
    return null;
  };

  // ========================== Active ==========================
  var _React$useState7 = React.useState(null),
    _React$useState8 = _slicedToArray(_React$useState7, 2),
    activeKey = _React$useState8[0],
    setActiveKey = _React$useState8[1];
  var activeEntity = keyEntities[activeKey];
  React.useEffect(function () {
    if (!open) {
      return;
    }
    var nextActiveKey = null;
    var getFirstNode = function getFirstNode() {
      var firstNode = getFirstMatchingNode(memoTreeData);
      return firstNode ? firstNode[fieldNames.value] : null;
    };

    // single mode active first checked node
    if (!multiple && checkedKeys.length && !searchValue) {
      nextActiveKey = checkedKeys[0];
    } else {
      nextActiveKey = getFirstNode();
    }
    setActiveKey(nextActiveKey);
  }, [open, searchValue]);

  // ========================= Keyboard =========================
  React.useImperativeHandle(ref, function () {
    var _treeRef$current2;
    return {
      scrollTo: (_treeRef$current2 = treeRef.current) === null || _treeRef$current2 === void 0 ? void 0 : _treeRef$current2.scrollTo,
      onKeyDown: function onKeyDown(event) {
        var _treeRef$current3;
        var which = event.which;
        switch (which) {
          // >>> Arrow keys
          case KeyCode.UP:
          case KeyCode.DOWN:
          case KeyCode.LEFT:
          case KeyCode.RIGHT:
            (_treeRef$current3 = treeRef.current) === null || _treeRef$current3 === void 0 || _treeRef$current3.onKeyDown(event);
            break;

          // >>> Select item
          case KeyCode.ENTER:
            {
              if (activeEntity) {
                var isNodeDisabled = nodeDisabled(activeEntity.node);
                var _ref = (activeEntity === null || activeEntity === void 0 ? void 0 : activeEntity.node) || {},
                  selectable = _ref.selectable,
                  value = _ref.value,
                  disabled = _ref.disabled;
                if (selectable !== false && !disabled && !isNodeDisabled) {
                  onInternalSelect(null, {
                    node: {
                      key: activeKey
                    },
                    selected: !checkedKeys.includes(value)
                  });
                }
              }
              break;
            }

          // >>> Close
          case KeyCode.ESC:
            {
              toggleOpen(false);
            }
        }
      },
      onKeyUp: function onKeyUp() {}
    };
  });
  var hasLoadDataFn = useMemo(function () {
    return searchValue ? false : true;
  }, [searchValue, treeExpandedKeys || expandedKeys], function (_ref2, _ref3) {
    var _ref4 = _slicedToArray(_ref2, 1),
      preSearchValue = _ref4[0];
    var _ref5 = _slicedToArray(_ref3, 2),
      nextSearchValue = _ref5[0],
      nextExcludeSearchExpandedKeys = _ref5[1];
    return preSearchValue !== nextSearchValue && !!(nextSearchValue || nextExcludeSearchExpandedKeys);
  });
  var syncLoadData = hasLoadDataFn ? loadData : null;

  // ========================== Render ==========================
  if (memoTreeData.length === 0) {
    return /*#__PURE__*/React.createElement("div", {
      role: "listbox",
      className: "".concat(prefixCls, "-empty"),
      onMouseDown: onListMouseDown
    }, notFoundContent);
  }
  var treeProps = {
    fieldNames: fieldNames
  };
  if (treeLoadedKeys) {
    treeProps.loadedKeys = treeLoadedKeys;
  }
  if (mergedExpandedKeys) {
    treeProps.expandedKeys = mergedExpandedKeys;
  }
  return /*#__PURE__*/React.createElement("div", {
    onMouseDown: onListMouseDown
  }, activeEntity && open && /*#__PURE__*/React.createElement("span", {
    style: HIDDEN_STYLE,
    "aria-live": "assertive"
  }, activeEntity.node.value), /*#__PURE__*/React.createElement(UnstableContext.Provider, {
    value: {
      nodeDisabled: nodeDisabled
    }
  }, /*#__PURE__*/React.createElement(Tree, _extends({
    ref: treeRef,
    focusable: false,
    prefixCls: "".concat(prefixCls, "-tree"),
    treeData: memoTreeData,
    height: listHeight,
    itemHeight: listItemHeight,
    itemScrollOffset: listItemScrollOffset,
    virtual: virtual !== false && dropdownMatchSelectWidth !== false,
    multiple: multiple,
    icon: treeIcon,
    showIcon: showTreeIcon,
    switcherIcon: switcherIcon,
    showLine: treeLine,
    loadData: syncLoadData,
    motion: treeMotion,
    activeKey: activeKey
    // We handle keys by out instead tree self
    ,
    checkable: checkable,
    checkStrictly: true,
    checkedKeys: mergedCheckedKeys,
    selectedKeys: !checkable ? checkedKeys : [],
    defaultExpandAll: treeDefaultExpandAll,
    titleRender: treeTitleRender
  }, treeProps, {
    // Proxy event out
    onActiveChange: setActiveKey,
    onSelect: onInternalSelect,
    onCheck: onInternalSelect,
    onExpand: onInternalExpand,
    onLoad: onTreeLoad,
    filterTreeNode: filterTreeNode,
    expandAction: treeExpandAction,
    onScroll: onPopupScroll
  }))));
};
var RefOptionList = /*#__PURE__*/React.forwardRef(OptionList);
if (process.env.NODE_ENV !== 'production') {
  RefOptionList.displayName = 'OptionList';
}
export default RefOptionList;