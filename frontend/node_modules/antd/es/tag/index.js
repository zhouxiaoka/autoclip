"use client";

var __rest = this && this.__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
import * as React from 'react';
import classNames from 'classnames';
import omit from "rc-util/es/omit";
import { isPresetColor, isPresetStatusColor } from '../_util/colors';
import useClosable, { pickClosable } from '../_util/hooks/useClosable';
import { replaceElement } from '../_util/reactNode';
import { devUseWarning } from '../_util/warning';
import Wave from '../_util/wave';
import { ConfigContext } from '../config-provider';
import CheckableTag from './CheckableTag';
import useStyle from './style';
import PresetCmp from './style/presetCmp';
import StatusCmp from './style/statusCmp';
const InternalTag = /*#__PURE__*/React.forwardRef((tagProps, ref) => {
  const {
      prefixCls: customizePrefixCls,
      className,
      rootClassName,
      style,
      children,
      icon,
      color,
      onClose,
      bordered = true,
      visible: deprecatedVisible
    } = tagProps,
    props = __rest(tagProps, ["prefixCls", "className", "rootClassName", "style", "children", "icon", "color", "onClose", "bordered", "visible"]);
  const {
    getPrefixCls,
    direction,
    tag: tagContext
  } = React.useContext(ConfigContext);
  const [visible, setVisible] = React.useState(true);
  const domProps = omit(props, ['closeIcon', 'closable']);
  // Warning for deprecated usage
  if (process.env.NODE_ENV !== 'production') {
    const warning = devUseWarning('Tag');
    warning.deprecated(!('visible' in tagProps), 'visible', 'visible && <Tag />');
  }
  React.useEffect(() => {
    if (deprecatedVisible !== undefined) {
      setVisible(deprecatedVisible);
    }
  }, [deprecatedVisible]);
  const isPreset = isPresetColor(color);
  const isStatus = isPresetStatusColor(color);
  const isInternalColor = isPreset || isStatus;
  const tagStyle = Object.assign(Object.assign({
    backgroundColor: color && !isInternalColor ? color : undefined
  }, tagContext === null || tagContext === void 0 ? void 0 : tagContext.style), style);
  const prefixCls = getPrefixCls('tag', customizePrefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = useStyle(prefixCls);
  // Style
  const tagClassName = classNames(prefixCls, tagContext === null || tagContext === void 0 ? void 0 : tagContext.className, {
    [`${prefixCls}-${color}`]: isInternalColor,
    [`${prefixCls}-has-color`]: color && !isInternalColor,
    [`${prefixCls}-hidden`]: !visible,
    [`${prefixCls}-rtl`]: direction === 'rtl',
    [`${prefixCls}-borderless`]: !bordered
  }, className, rootClassName, hashId, cssVarCls);
  const handleCloseClick = e => {
    e.stopPropagation();
    onClose === null || onClose === void 0 ? void 0 : onClose(e);
    if (e.defaultPrevented) {
      return;
    }
    setVisible(false);
  };
  const [, mergedCloseIcon] = useClosable(pickClosable(tagProps), pickClosable(tagContext), {
    closable: false,
    closeIconRender: iconNode => {
      const replacement = /*#__PURE__*/React.createElement("span", {
        className: `${prefixCls}-close-icon`,
        onClick: handleCloseClick
      }, iconNode);
      return replaceElement(iconNode, replacement, originProps => ({
        onClick: e => {
          var _a;
          (_a = originProps === null || originProps === void 0 ? void 0 : originProps.onClick) === null || _a === void 0 ? void 0 : _a.call(originProps, e);
          handleCloseClick(e);
        },
        className: classNames(originProps === null || originProps === void 0 ? void 0 : originProps.className, `${prefixCls}-close-icon`)
      }));
    }
  });
  const isNeedWave = typeof props.onClick === 'function' || children && children.type === 'a';
  const iconNode = icon || null;
  const kids = iconNode ? (/*#__PURE__*/React.createElement(React.Fragment, null, iconNode, children && /*#__PURE__*/React.createElement("span", null, children))) : children;
  const tagNode = /*#__PURE__*/React.createElement("span", Object.assign({}, domProps, {
    ref: ref,
    className: tagClassName,
    style: tagStyle
  }), kids, mergedCloseIcon, isPreset && /*#__PURE__*/React.createElement(PresetCmp, {
    key: "preset",
    prefixCls: prefixCls
  }), isStatus && /*#__PURE__*/React.createElement(StatusCmp, {
    key: "status",
    prefixCls: prefixCls
  }));
  return wrapCSSVar(isNeedWave ? /*#__PURE__*/React.createElement(Wave, {
    component: "Tag"
  }, tagNode) : tagNode);
});
const Tag = InternalTag;
if (process.env.NODE_ENV !== 'production') {
  Tag.displayName = 'Tag';
}
Tag.CheckableTag = CheckableTag;
export default Tag;