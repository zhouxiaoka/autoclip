"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.genSubStyleComponent = exports.genStyleHooks = exports.genComponentStyleHook = void 0;
var _react = require("react");
var _cssinjsUtils = require("@ant-design/cssinjs-utils");
var _context = require("../../config-provider/context");
var _style = require("../../style");
var _useToken = _interopRequireWildcard(require("../useToken"));
const {
  genStyleHooks,
  genComponentStyleHook,
  genSubStyleComponent
} = (0, _cssinjsUtils.genStyleUtils)({
  usePrefix: () => {
    const {
      getPrefixCls,
      iconPrefixCls
    } = (0, _react.useContext)(_context.ConfigContext);
    const rootPrefixCls = getPrefixCls();
    return {
      rootPrefixCls,
      iconPrefixCls
    };
  },
  useToken: () => {
    const [theme, realToken, hashId, token, cssVar] = (0, _useToken.default)();
    return {
      theme,
      realToken,
      hashId,
      token,
      cssVar
    };
  },
  useCSP: () => {
    const {
      csp
    } = (0, _react.useContext)(_context.ConfigContext);
    return csp !== null && csp !== void 0 ? csp : {};
  },
  getResetStyles: (token, config) => {
    var _a;
    const linkStyle = (0, _style.genLinkStyle)(token);
    return [linkStyle, {
      '&': linkStyle
    }, (0, _style.genIconStyle)((_a = config === null || config === void 0 ? void 0 : config.prefix.iconPrefixCls) !== null && _a !== void 0 ? _a : _context.defaultIconPrefixCls)];
  },
  getCommonStyle: _style.genCommonStyle,
  getCompUnitless: () => _useToken.unitless
});
exports.genSubStyleComponent = genSubStyleComponent;
exports.genComponentStyleHook = genComponentStyleHook;
exports.genStyleHooks = genStyleHooks;