"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _react = require("react");
const useTooltipProps = (tooltip, editConfigText, children) => (0, _react.useMemo)(() => {
  if (tooltip === true) {
    return {
      title: editConfigText !== null && editConfigText !== void 0 ? editConfigText : children
    };
  }
  if (/*#__PURE__*/(0, _react.isValidElement)(tooltip)) {
    return {
      title: tooltip
    };
  }
  if (typeof tooltip === 'object') {
    return Object.assign({
      title: editConfigText !== null && editConfigText !== void 0 ? editConfigText : children
    }, tooltip);
  }
  return {
    title: tooltip
  };
}, [tooltip, editConfigText, children]);
var _default = exports.default = useTooltipProps;