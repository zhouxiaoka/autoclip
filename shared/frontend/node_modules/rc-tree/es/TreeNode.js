import _extends from "@babel/runtime/helpers/esm/extends";
import _defineProperty from "@babel/runtime/helpers/esm/defineProperty";
import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import _slicedToArray from "@babel/runtime/helpers/esm/slicedToArray";
import _objectWithoutProperties from "@babel/runtime/helpers/esm/objectWithoutProperties";
var _excluded = ["eventKey", "className", "style", "dragOver", "dragOverGapTop", "dragOverGapBottom", "isLeaf", "isStart", "isEnd", "expanded", "selected", "checked", "halfChecked", "loading", "domRef", "active", "data", "onMouseMove", "selectable"];
import React from 'react';
import classNames from 'classnames';
import pickAttrs from "rc-util/es/pickAttrs";
import { TreeContext, UnstableContext } from "./contextTypes";
import Indent from "./Indent";
import getEntity from "./utils/keyUtil";
import { convertNodePropsToEventData } from "./utils/treeUtil";
var ICON_OPEN = 'open';
var ICON_CLOSE = 'close';
var defaultTitle = '---';
var TreeNode = function TreeNode(props) {
  var _unstableContext$node, _context$filterTreeNo, _classNames4;
  var eventKey = props.eventKey,
    className = props.className,
    style = props.style,
    dragOver = props.dragOver,
    dragOverGapTop = props.dragOverGapTop,
    dragOverGapBottom = props.dragOverGapBottom,
    isLeaf = props.isLeaf,
    isStart = props.isStart,
    isEnd = props.isEnd,
    expanded = props.expanded,
    selected = props.selected,
    checked = props.checked,
    halfChecked = props.halfChecked,
    loading = props.loading,
    domRef = props.domRef,
    active = props.active,
    data = props.data,
    onMouseMove = props.onMouseMove,
    selectable = props.selectable,
    otherProps = _objectWithoutProperties(props, _excluded);
  var context = React.useContext(TreeContext);
  var unstableContext = React.useContext(UnstableContext);
  var selectHandleRef = React.useRef(null);
  var _React$useState = React.useState(false),
    _React$useState2 = _slicedToArray(_React$useState, 2),
    dragNodeHighlight = _React$useState2[0],
    setDragNodeHighlight = _React$useState2[1];

  // ======= State: Disabled State =======
  var isDisabled = !!(context.disabled || props.disabled || (_unstableContext$node = unstableContext.nodeDisabled) !== null && _unstableContext$node !== void 0 && _unstableContext$node.call(unstableContext, data));
  var isCheckable = React.useMemo(function () {
    // Return false if tree or treeNode is not checkable
    if (!context.checkable || props.checkable === false) {
      return false;
    }
    return context.checkable;
  }, [context.checkable, props.checkable]);

  // ======= Event Handlers: Selection and Check =======
  var onSelect = function onSelect(e) {
    if (isDisabled) {
      return;
    }
    context.onNodeSelect(e, convertNodePropsToEventData(props));
  };
  var onCheck = function onCheck(e) {
    if (isDisabled) {
      return;
    }
    if (!isCheckable || props.disableCheckbox) {
      return;
    }
    context.onNodeCheck(e, convertNodePropsToEventData(props), !checked);
  };

  // ======= State: Selectable Check =======
  var isSelectable = React.useMemo(function () {
    // Ignore when selectable is undefined or null
    if (typeof selectable === 'boolean') {
      return selectable;
    }
    return context.selectable;
  }, [selectable, context.selectable]);
  var onSelectorClick = function onSelectorClick(e) {
    // Click trigger before select/check operation
    context.onNodeClick(e, convertNodePropsToEventData(props));
    if (isSelectable) {
      onSelect(e);
    } else {
      onCheck(e);
    }
  };
  var onSelectorDoubleClick = function onSelectorDoubleClick(e) {
    context.onNodeDoubleClick(e, convertNodePropsToEventData(props));
  };
  var onMouseEnter = function onMouseEnter(e) {
    context.onNodeMouseEnter(e, convertNodePropsToEventData(props));
  };
  var onMouseLeave = function onMouseLeave(e) {
    context.onNodeMouseLeave(e, convertNodePropsToEventData(props));
  };
  var onContextMenu = function onContextMenu(e) {
    context.onNodeContextMenu(e, convertNodePropsToEventData(props));
  };

  // ======= Drag: Drag Enabled =======
  var isDraggable = React.useMemo(function () {
    return !!(context.draggable && (!context.draggable.nodeDraggable || context.draggable.nodeDraggable(data)));
  }, [context.draggable, data]);

  // ======= Drag: Drag Event Handlers =======
  var onDragStart = function onDragStart(e) {
    e.stopPropagation();
    setDragNodeHighlight(true);
    context.onNodeDragStart(e, props);
    try {
      // ie throw error
      // firefox-need-it
      e.dataTransfer.setData('text/plain', '');
    } catch (_unused) {
      // empty
    }
  };
  var onDragEnter = function onDragEnter(e) {
    e.preventDefault();
    e.stopPropagation();
    context.onNodeDragEnter(e, props);
  };
  var onDragOver = function onDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    context.onNodeDragOver(e, props);
  };
  var onDragLeave = function onDragLeave(e) {
    e.stopPropagation();
    context.onNodeDragLeave(e, props);
  };
  var onDragEnd = function onDragEnd(e) {
    e.stopPropagation();
    setDragNodeHighlight(false);
    context.onNodeDragEnd(e, props);
  };
  var onDrop = function onDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    setDragNodeHighlight(false);
    context.onNodeDrop(e, props);
  };

  // ======= Expand: Node Expansion =======
  var onExpand = function onExpand(e) {
    if (loading) {
      return;
    }
    context.onNodeExpand(e, convertNodePropsToEventData(props));
  };

  // ======= State: Has Children =======
  var hasChildren = React.useMemo(function () {
    var _ref = getEntity(context.keyEntities, eventKey) || {},
      children = _ref.children;
    return Boolean((children || []).length);
  }, [context.keyEntities, eventKey]);

  // ======= State: Leaf Check =======
  var memoizedIsLeaf = React.useMemo(function () {
    if (isLeaf === false) {
      return false;
    }
    return isLeaf || !context.loadData && !hasChildren || context.loadData && props.loaded && !hasChildren;
  }, [isLeaf, context.loadData, hasChildren, props.loaded]);

  // ============== Effect ==============
  React.useEffect(function () {
    // Load data to avoid default expanded tree without data
    if (loading) {
      return;
    }
    // read from state to avoid loadData at same time
    if (typeof context.loadData === 'function' && expanded && !memoizedIsLeaf && !props.loaded) {
      // We needn't reload data when has children in sync logic
      // It's only needed in node expanded
      context.onNodeLoad(convertNodePropsToEventData(props));
    }
  }, [loading, context.loadData, context.onNodeLoad, expanded, memoizedIsLeaf, props]);

  // ==================== Render: Drag Handler ====================
  var dragHandlerNode = React.useMemo(function () {
    var _context$draggable;
    if (!((_context$draggable = context.draggable) !== null && _context$draggable !== void 0 && _context$draggable.icon)) {
      return null;
    }
    return /*#__PURE__*/React.createElement("span", {
      className: "".concat(context.prefixCls, "-draggable-icon")
    }, context.draggable.icon);
  }, [context.draggable]);

  // ====================== Render: Switcher ======================
  var renderSwitcherIconDom = function renderSwitcherIconDom(isInternalLeaf) {
    var switcherIcon = props.switcherIcon || context.switcherIcon;
    // if switcherIconDom is null, no render switcher span
    if (typeof switcherIcon === 'function') {
      return switcherIcon(_objectSpread(_objectSpread({}, props), {}, {
        isLeaf: isInternalLeaf
      }));
    }
    return switcherIcon;
  };

  // Switcher
  var renderSwitcher = function renderSwitcher() {
    if (memoizedIsLeaf) {
      // if switcherIconDom is null, no render switcher span
      var _switcherIconDom = renderSwitcherIconDom(true);
      return _switcherIconDom !== false ? /*#__PURE__*/React.createElement("span", {
        className: classNames("".concat(context.prefixCls, "-switcher"), "".concat(context.prefixCls, "-switcher-noop"))
      }, _switcherIconDom) : null;
    }
    var switcherIconDom = renderSwitcherIconDom(false);
    return switcherIconDom !== false ? /*#__PURE__*/React.createElement("span", {
      onClick: onExpand,
      className: classNames("".concat(context.prefixCls, "-switcher"), "".concat(context.prefixCls, "-switcher_").concat(expanded ? ICON_OPEN : ICON_CLOSE))
    }, switcherIconDom) : null;
  };

  // ====================== Checkbox ======================
  var checkboxNode = React.useMemo(function () {
    if (!isCheckable) {
      return null;
    }

    // [Legacy] Custom element should be separate with `checkable` in future
    var $custom = typeof isCheckable !== 'boolean' ? isCheckable : null;
    return /*#__PURE__*/React.createElement("span", {
      className: classNames("".concat(context.prefixCls, "-checkbox"), _defineProperty(_defineProperty(_defineProperty({}, "".concat(context.prefixCls, "-checkbox-checked"), checked), "".concat(context.prefixCls, "-checkbox-indeterminate"), !checked && halfChecked), "".concat(context.prefixCls, "-checkbox-disabled"), isDisabled || props.disableCheckbox)),
      onClick: onCheck,
      role: "checkbox",
      "aria-checked": halfChecked ? 'mixed' : checked,
      "aria-disabled": isDisabled || props.disableCheckbox,
      "aria-label": "Select ".concat(typeof props.title === 'string' ? props.title : 'tree node')
    }, $custom);
  }, [isCheckable, checked, halfChecked, isDisabled, props.disableCheckbox, props.title]);

  // ============== State: Node State (Open/Close) ==============
  var nodeState = React.useMemo(function () {
    if (memoizedIsLeaf) {
      return null;
    }
    return expanded ? ICON_OPEN : ICON_CLOSE;
  }, [memoizedIsLeaf, expanded]);

  // ==================== Render: Title + Icon ====================
  var iconNode = React.useMemo(function () {
    return /*#__PURE__*/React.createElement("span", {
      className: classNames("".concat(context.prefixCls, "-iconEle"), "".concat(context.prefixCls, "-icon__").concat(nodeState || 'docu'), _defineProperty({}, "".concat(context.prefixCls, "-icon_loading"), loading))
    });
  }, [context.prefixCls, nodeState, loading]);

  // =================== Drop Indicator ===================
  var dropIndicatorNode = React.useMemo(function () {
    var rootDraggable = Boolean(context.draggable);
    // allowDrop is calculated in Tree.tsx, there is no need for calc it here
    var showIndicator = !props.disabled && rootDraggable && context.dragOverNodeKey === eventKey;
    if (!showIndicator) {
      return null;
    }
    return context.dropIndicatorRender({
      dropPosition: context.dropPosition,
      dropLevelOffset: context.dropLevelOffset,
      indent: context.indent,
      prefixCls: context.prefixCls,
      direction: context.direction
    });
  }, [context.dropPosition, context.dropLevelOffset, context.indent, context.prefixCls, context.direction, context.draggable, context.dragOverNodeKey, context.dropIndicatorRender]);

  // Icon + Title
  var selectorNode = React.useMemo(function () {
    var _props$title = props.title,
      title = _props$title === void 0 ? defaultTitle : _props$title;
    var wrapClass = "".concat(context.prefixCls, "-node-content-wrapper");

    // Icon - Still show loading icon when loading without showIcon
    var $icon;
    if (context.showIcon) {
      var currentIcon = props.icon || context.icon;
      $icon = currentIcon ? /*#__PURE__*/React.createElement("span", {
        className: classNames("".concat(context.prefixCls, "-iconEle"), "".concat(context.prefixCls, "-icon__customize"))
      }, typeof currentIcon === 'function' ? currentIcon(props) : currentIcon) : iconNode;
    } else if (context.loadData && loading) {
      $icon = iconNode;
    }

    // Title
    var titleNode;
    if (typeof title === 'function') {
      titleNode = title(data);
    } else if (context.titleRender) {
      titleNode = context.titleRender(data);
    } else {
      titleNode = title;
    }
    return /*#__PURE__*/React.createElement("span", {
      ref: selectHandleRef,
      title: typeof title === 'string' ? title : '',
      className: classNames(wrapClass, "".concat(wrapClass, "-").concat(nodeState || 'normal'), _defineProperty({}, "".concat(context.prefixCls, "-node-selected"), !isDisabled && (selected || dragNodeHighlight))),
      onMouseEnter: onMouseEnter,
      onMouseLeave: onMouseLeave,
      onContextMenu: onContextMenu,
      onClick: onSelectorClick,
      onDoubleClick: onSelectorDoubleClick
    }, $icon, /*#__PURE__*/React.createElement("span", {
      className: "".concat(context.prefixCls, "-title")
    }, titleNode), dropIndicatorNode);
  }, [context.prefixCls, context.showIcon, props, context.icon, iconNode, context.titleRender, data, nodeState, onMouseEnter, onMouseLeave, onContextMenu, onSelectorClick, onSelectorDoubleClick]);
  var dataOrAriaAttributeProps = pickAttrs(otherProps, {
    aria: true,
    data: true
  });
  var _ref2 = getEntity(context.keyEntities, eventKey) || {},
    level = _ref2.level;
  var isEndNode = isEnd[isEnd.length - 1];
  var draggableWithoutDisabled = !isDisabled && isDraggable;
  var dragging = context.draggingNodeKey === eventKey;
  var ariaSelected = selectable !== undefined ? {
    'aria-selected': !!selectable
  } : undefined;
  return /*#__PURE__*/React.createElement("div", _extends({
    ref: domRef,
    role: "treeitem",
    "aria-expanded": isLeaf ? undefined : expanded,
    className: classNames(className, "".concat(context.prefixCls, "-treenode"), (_classNames4 = {}, _defineProperty(_defineProperty(_defineProperty(_defineProperty(_defineProperty(_defineProperty(_defineProperty(_defineProperty(_defineProperty(_defineProperty(_classNames4, "".concat(context.prefixCls, "-treenode-disabled"), isDisabled), "".concat(context.prefixCls, "-treenode-switcher-").concat(expanded ? 'open' : 'close'), !isLeaf), "".concat(context.prefixCls, "-treenode-checkbox-checked"), checked), "".concat(context.prefixCls, "-treenode-checkbox-indeterminate"), halfChecked), "".concat(context.prefixCls, "-treenode-selected"), selected), "".concat(context.prefixCls, "-treenode-loading"), loading), "".concat(context.prefixCls, "-treenode-active"), active), "".concat(context.prefixCls, "-treenode-leaf-last"), isEndNode), "".concat(context.prefixCls, "-treenode-draggable"), isDraggable), "dragging", dragging), _defineProperty(_defineProperty(_defineProperty(_defineProperty(_defineProperty(_defineProperty(_defineProperty(_classNames4, 'drop-target', context.dropTargetKey === eventKey), 'drop-container', context.dropContainerKey === eventKey), 'drag-over', !isDisabled && dragOver), 'drag-over-gap-top', !isDisabled && dragOverGapTop), 'drag-over-gap-bottom', !isDisabled && dragOverGapBottom), 'filter-node', (_context$filterTreeNo = context.filterTreeNode) === null || _context$filterTreeNo === void 0 ? void 0 : _context$filterTreeNo.call(context, convertNodePropsToEventData(props))), "".concat(context.prefixCls, "-treenode-leaf"), memoizedIsLeaf))),
    style: style
    // Draggable config
    ,
    draggable: draggableWithoutDisabled,
    onDragStart: draggableWithoutDisabled ? onDragStart : undefined
    // Drop config
    ,
    onDragEnter: isDraggable ? onDragEnter : undefined,
    onDragOver: isDraggable ? onDragOver : undefined,
    onDragLeave: isDraggable ? onDragLeave : undefined,
    onDrop: isDraggable ? onDrop : undefined,
    onDragEnd: isDraggable ? onDragEnd : undefined,
    onMouseMove: onMouseMove
  }, ariaSelected, dataOrAriaAttributeProps), /*#__PURE__*/React.createElement(Indent, {
    prefixCls: context.prefixCls,
    level: level,
    isStart: isStart,
    isEnd: isEnd
  }), dragHandlerNode, renderSwitcher(), checkboxNode, selectorNode);
};
TreeNode.isTreeNode = 1;
if (process.env.NODE_ENV !== 'production') {
  TreeNode.displayName = 'TreeNode';
}
export default TreeNode;