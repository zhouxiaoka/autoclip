"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");
var _typeof3 = require("@babel/runtime/helpers/typeof");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.parseItems = parseItems;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _extends2 = _interopRequireDefault(require("@babel/runtime/helpers/extends"));
var _objectWithoutProperties2 = _interopRequireDefault(require("@babel/runtime/helpers/objectWithoutProperties"));
var _typeof2 = _interopRequireDefault(require("@babel/runtime/helpers/typeof"));
var React = _interopRequireWildcard(require("react"));
var _Divider = _interopRequireDefault(require("../Divider"));
var _MenuItem = _interopRequireDefault(require("../MenuItem"));
var _MenuItemGroup = _interopRequireDefault(require("../MenuItemGroup"));
var _SubMenu = _interopRequireDefault(require("../SubMenu"));
var _commonUtil = require("./commonUtil");
var _excluded = ["label", "children", "key", "type", "extra"];
function _getRequireWildcardCache(e) { if ("function" != typeof WeakMap) return null; var r = new WeakMap(), t = new WeakMap(); return (_getRequireWildcardCache = function _getRequireWildcardCache(e) { return e ? t : r; })(e); }
function _interopRequireWildcard(e, r) { if (!r && e && e.__esModule) return e; if (null === e || "object" != _typeof3(e) && "function" != typeof e) return { default: e }; var t = _getRequireWildcardCache(r); if (t && t.has(e)) return t.get(e); var n = { __proto__: null }, a = Object.defineProperty && Object.getOwnPropertyDescriptor; for (var u in e) if ("default" !== u && Object.prototype.hasOwnProperty.call(e, u)) { var i = a ? Object.getOwnPropertyDescriptor(e, u) : null; i && (i.get || i.set) ? Object.defineProperty(n, u, i) : n[u] = e[u]; } return n.default = e, t && t.set(e, n), n; }
function convertItemsToNodes(list, components, prefixCls) {
  var MergedMenuItem = components.item,
    MergedMenuItemGroup = components.group,
    MergedSubMenu = components.submenu,
    MergedDivider = components.divider;
  return (list || []).map(function (opt, index) {
    if (opt && (0, _typeof2.default)(opt) === 'object') {
      var _ref = opt,
        label = _ref.label,
        children = _ref.children,
        key = _ref.key,
        type = _ref.type,
        extra = _ref.extra,
        restProps = (0, _objectWithoutProperties2.default)(_ref, _excluded);
      var mergedKey = key !== null && key !== void 0 ? key : "tmp-".concat(index);

      // MenuItemGroup & SubMenuItem
      if (children || type === 'group') {
        if (type === 'group') {
          // Group
          return /*#__PURE__*/React.createElement(MergedMenuItemGroup, (0, _extends2.default)({
            key: mergedKey
          }, restProps, {
            title: label
          }), convertItemsToNodes(children, components, prefixCls));
        }

        // Sub Menu
        return /*#__PURE__*/React.createElement(MergedSubMenu, (0, _extends2.default)({
          key: mergedKey
        }, restProps, {
          title: label
        }), convertItemsToNodes(children, components, prefixCls));
      }

      // MenuItem & Divider
      if (type === 'divider') {
        return /*#__PURE__*/React.createElement(MergedDivider, (0, _extends2.default)({
          key: mergedKey
        }, restProps));
      }
      return /*#__PURE__*/React.createElement(MergedMenuItem, (0, _extends2.default)({
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
function parseItems(children, items, keyPath, components, prefixCls) {
  var childNodes = children;
  var mergedComponents = (0, _objectSpread2.default)({
    divider: _Divider.default,
    item: _MenuItem.default,
    group: _MenuItemGroup.default,
    submenu: _SubMenu.default
  }, components);
  if (items) {
    childNodes = convertItemsToNodes(items, mergedComponents, prefixCls);
  }
  return (0, _commonUtil.parseChildren)(childNodes, keyPath);
}