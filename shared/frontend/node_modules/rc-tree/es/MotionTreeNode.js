import _extends from "@babel/runtime/helpers/esm/extends";
import _objectDestructuringEmpty from "@babel/runtime/helpers/esm/objectDestructuringEmpty";
import _slicedToArray from "@babel/runtime/helpers/esm/slicedToArray";
import _objectWithoutProperties from "@babel/runtime/helpers/esm/objectWithoutProperties";
var _excluded = ["className", "style", "motion", "motionNodes", "motionType", "onMotionStart", "onMotionEnd", "active", "treeNodeRequiredProps"];
import classNames from 'classnames';
import CSSMotion from 'rc-motion';
import useLayoutEffect from "rc-util/es/hooks/useLayoutEffect";
import * as React from 'react';
import { TreeContext } from "./contextTypes";
import TreeNode from "./TreeNode";
import useUnmount from "./useUnmount";
import { getTreeNodeProps } from "./utils/treeUtil";
var MotionTreeNode = /*#__PURE__*/React.forwardRef(function (oriProps, ref) {
  var className = oriProps.className,
    style = oriProps.style,
    motion = oriProps.motion,
    motionNodes = oriProps.motionNodes,
    motionType = oriProps.motionType,
    onOriginMotionStart = oriProps.onMotionStart,
    onOriginMotionEnd = oriProps.onMotionEnd,
    active = oriProps.active,
    treeNodeRequiredProps = oriProps.treeNodeRequiredProps,
    props = _objectWithoutProperties(oriProps, _excluded);
  var _React$useState = React.useState(true),
    _React$useState2 = _slicedToArray(_React$useState, 2),
    visible = _React$useState2[0],
    setVisible = _React$useState2[1];
  var _React$useContext = React.useContext(TreeContext),
    prefixCls = _React$useContext.prefixCls;

  // Calculate target visible here.
  // And apply in effect to make `leave` motion work.
  var targetVisible = motionNodes && motionType !== 'hide';
  useLayoutEffect(function () {
    if (motionNodes) {
      if (targetVisible !== visible) {
        setVisible(targetVisible);
      }
    }
  }, [motionNodes]);
  var triggerMotionStart = function triggerMotionStart() {
    if (motionNodes) {
      onOriginMotionStart();
    }
  };

  // Should only trigger once
  var triggerMotionEndRef = React.useRef(false);
  var triggerMotionEnd = function triggerMotionEnd() {
    if (motionNodes && !triggerMotionEndRef.current) {
      triggerMotionEndRef.current = true;
      onOriginMotionEnd();
    }
  };

  // Effect if unmount
  useUnmount(triggerMotionStart, triggerMotionEnd);

  // Motion end event
  var onVisibleChanged = function onVisibleChanged(nextVisible) {
    if (targetVisible === nextVisible) {
      triggerMotionEnd();
    }
  };
  if (motionNodes) {
    return /*#__PURE__*/React.createElement(CSSMotion, _extends({
      ref: ref,
      visible: visible
    }, motion, {
      motionAppear: motionType === 'show',
      onVisibleChanged: onVisibleChanged
    }), function (_ref, motionRef) {
      var motionClassName = _ref.className,
        motionStyle = _ref.style;
      return /*#__PURE__*/React.createElement("div", {
        ref: motionRef,
        className: classNames("".concat(prefixCls, "-treenode-motion"), motionClassName),
        style: motionStyle
      }, motionNodes.map(function (treeNode) {
        var restProps = Object.assign({}, (_objectDestructuringEmpty(treeNode.data), treeNode.data)),
          title = treeNode.title,
          key = treeNode.key,
          isStart = treeNode.isStart,
          isEnd = treeNode.isEnd;
        delete restProps.children;
        var treeNodeProps = getTreeNodeProps(key, treeNodeRequiredProps);
        return /*#__PURE__*/React.createElement(TreeNode, _extends({}, restProps, treeNodeProps, {
          title: title,
          active: active,
          data: treeNode.data,
          key: key,
          isStart: isStart,
          isEnd: isEnd
        }));
      }));
    });
  }
  return /*#__PURE__*/React.createElement(TreeNode, _extends({
    domRef: ref,
    className: className,
    style: style
  }, props, {
    active: active
  }));
});
if (process.env.NODE_ENV !== 'production') {
  MotionTreeNode.displayName = 'MotionTreeNode';
}
export default MotionTreeNode;