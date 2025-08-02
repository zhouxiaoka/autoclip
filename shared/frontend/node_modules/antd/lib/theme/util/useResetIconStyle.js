"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _cssinjs = require("@ant-design/cssinjs");
var _style = require("../../style");
var _useToken = _interopRequireDefault(require("../useToken"));
const useResetIconStyle = (iconPrefixCls, csp) => {
  const [theme, token] = (0, _useToken.default)();
  // Generate style for icons
  return (0, _cssinjs.useStyleRegister)({
    theme,
    token,
    hashId: '',
    path: ['ant-design-icons', iconPrefixCls],
    nonce: () => csp === null || csp === void 0 ? void 0 : csp.nonce,
    layer: {
      name: 'antd'
    }
  }, () => [(0, _style.genIconStyle)(iconPrefixCls)]);
};
var _default = exports.default = useResetIconStyle;