import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import _extends from "@babel/runtime/helpers/esm/extends";
import _objectWithoutProperties from "@babel/runtime/helpers/esm/objectWithoutProperties";
import _typeof from "@babel/runtime/helpers/esm/typeof";
var _excluded = ["label", "children", "key", "type", "extra"];
import * as React from 'react';
import Divider from "../Divider";
import MenuItem from "../MenuItem";
import MenuItemGroup from "../MenuItemGroup";
import SubMenu from "../SubMenu";
import { parseChildren } from "./commonUtil";
function convertItemsToNodes(list, components, prefixCls) {
  var MergedMenuItem = components.item,
    MergedMenuItemGroup = components.group,
    MergedSubMenu = components.submenu,
    MergedDivider = components.divider;
  return (list || []).map(function (opt, index) {
    if (opt && _typeof(opt) === 'object') {
      var _ref = opt,
        label = _ref.label,
        children = _ref.children,
        key = _ref.key,
        type = _ref.type,
        extra = _ref.extra,
        restProps = _objectWithoutProperties(_ref, _excluded);
      var mergedKey = key !== null && key !== void 0 ? key : "tmp-".concat(index);

      // MenuItemGroup & SubMenuItem
      if (children || type === 'group') {
        if (type === 'group') {
          // Group
          return /*#__PURE__*/React.createElement(MergedMenuItemGroup, _extends({
            key: mergedKey
          }, restProps, {
            title: label
          }), convertItemsToNodes(children, components, prefixCls));
        }

        // Sub Menu
        return /*#__PURE__*/React.createElement(MergedSubMenu, _extends({
          key: mergedKey
        }, restProps, {
          title: label
        }), convertItemsToNodes(children, components, prefixCls));
      }

      // MenuItem & Divider
      if (type === 'divider') {
        return /*#__PURE__*/React.createElement(MergedDivider, _extends({
          key: mergedKey
        }, restProps));
      }
      return /*#__PURE__*/React.createElement(MergedMenuItem, _extends({
        key: mergedKey
      }, restProps, {
        extra: extra
      }), label, (!!extra || extra === 0) && /*#__PURE__*/React.createElement("span", {
        className: "".concat(prefixCls, "-item-extra")
      }, extra));
    }
    return null;
  }).filter(function (opt) {
    return opt;
  });
}
export function parseItems(children, items, keyPath, components, prefixCls) {
  var childNodes = children;
  var mergedComponents = _objectSpread({
    divider: Divider,
    item: MenuItem,
    group: MenuItemGroup,
    submenu: SubMenu
  }, components);
  if (items) {
    childNodes = convertItemsToNodes(items, mergedComponents, prefixCls);
  }
  return parseChildren(childNodes, keyPath);
}