"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = exports.Meta = void 0;
var _react = _interopRequireWildcard(require("react"));
var _classnames = _interopRequireDefault(require("classnames"));
var _reactNode = require("../_util/reactNode");
var _configProvider = require("../config-provider");
var _grid = require("../grid");
var _context = require("./context");
var __rest = void 0 && (void 0).__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
const Meta = _a => {
  var {
      prefixCls: customizePrefixCls,
      className,
      avatar,
      title,
      description
    } = _a,
    others = __rest(_a, ["prefixCls", "className", "avatar", "title", "description"]);
  const {
    getPrefixCls
  } = (0, _react.useContext)(_configProvider.ConfigContext);
  const prefixCls = getPrefixCls('list', customizePrefixCls);
  const classString = (0, _classnames.default)(`${prefixCls}-item-meta`, className);
  const content = /*#__PURE__*/_react.default.createElement("div", {
    className: `${prefixCls}-item-meta-content`
  }, title && /*#__PURE__*/_react.default.createElement("h4", {
    className: `${prefixCls}-item-meta-title`
  }, title), description && /*#__PURE__*/_react.default.createElement("div", {
    className: `${prefixCls}-item-meta-description`
  }, description));
  return /*#__PURE__*/_react.default.createElement("div", Object.assign({}, others, {
    className: classString
  }), avatar && /*#__PURE__*/_react.default.createElement("div", {
    className: `${prefixCls}-item-meta-avatar`
  }, avatar), (title || description) && content);
};
exports.Meta = Meta;
const InternalItem = /*#__PURE__*/_react.default.forwardRef((props, ref) => {
  const {
      prefixCls: customizePrefixCls,
      children,
      actions,
      extra,
      styles,
      className,
      classNames: customizeClassNames,
      colStyle
    } = props,
    others = __rest(props, ["prefixCls", "children", "actions", "extra", "styles", "className", "classNames", "colStyle"]);
  const {
    grid,
    itemLayout
  } = (0, _react.useContext)(_context.ListContext);
  const {
    getPrefixCls,
    list
  } = (0, _react.useContext)(_configProvider.ConfigContext);
  const moduleClass = moduleName => {
    var _a, _b;
    return (0, _classnames.default)((_b = (_a = list === null || list === void 0 ? void 0 : list.item) === null || _a === void 0 ? void 0 : _a.classNames) === null || _b === void 0 ? void 0 : _b[moduleName], customizeClassNames === null || customizeClassNames === void 0 ? void 0 : customizeClassNames[moduleName]);
  };
  const moduleStyle = moduleName => {
    var _a, _b;
    return Object.assign(Object.assign({}, (_b = (_a = list === null || list === void 0 ? void 0 : list.item) === null || _a === void 0 ? void 0 : _a.styles) === null || _b === void 0 ? void 0 : _b[moduleName]), styles === null || styles === void 0 ? void 0 : styles[moduleName]);
  };
  const isItemContainsTextNodeAndNotSingular = () => {
    let result = false;
    _react.Children.forEach(children, element => {
      if (typeof element === 'string') {
        result = true;
      }
    });
    return result && _react.Children.count(children) > 1;
  };
  const isFlexMode = () => {
    if (itemLayout === 'vertical') {
      return !!extra;
    }
    return !isItemContainsTextNodeAndNotSingular();
  };
  const prefixCls = getPrefixCls('list', customizePrefixCls);
  const actionsContent = actions && actions.length > 0 && (/*#__PURE__*/_react.default.createElement("ul", {
    className: (0, _classnames.default)(`${prefixCls}-item-action`, moduleClass('actions')),
    key: "actions",
    style: moduleStyle('actions')
  }, actions.map((action, i) => (
  /*#__PURE__*/
  // eslint-disable-next-line react/no-array-index-key
  _react.default.createElement("li", {
    key: `${prefixCls}-item-action-${i}`
  }, action, i !== actions.length - 1 && /*#__PURE__*/_react.default.createElement("em", {
    className: `${prefixCls}-item-action-split`
  }))))));
  const Element = grid ? 'div' : 'li';
  const itemChildren = /*#__PURE__*/_react.default.createElement(Element, Object.assign({}, others, !grid ? {
    ref
  } : {}, {
    className: (0, _classnames.default)(`${prefixCls}-item`, {
      [`${prefixCls}-item-no-flex`]: !isFlexMode()
    }, className)
  }), itemLayout === 'vertical' && extra ? [/*#__PURE__*/_react.default.createElement("div", {
    className: `${prefixCls}-item-main`,
    key: "content"
  }, children, actionsContent), /*#__PURE__*/_react.default.createElement("div", {
    className: (0, _classnames.default)(`${prefixCls}-item-extra`, moduleClass('extra')),
    key: "extra",
    style: moduleStyle('extra')
  }, extra)] : [children, actionsContent, (0, _reactNode.cloneElement)(extra, {
    key: 'extra'
  })]);
  return grid ? (/*#__PURE__*/_react.default.createElement(_grid.Col, {
    ref: ref,
    flex: 1,
    style: colStyle
  }, itemChildren)) : itemChildren;
});
const Item = InternalItem;
Item.Meta = Meta;
var _default = exports.default = Item;