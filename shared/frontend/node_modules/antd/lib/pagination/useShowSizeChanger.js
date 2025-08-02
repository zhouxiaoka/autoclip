"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = useShowSizeChanger;
var _react = require("react");
function useShowSizeChanger(showSizeChanger) {
  return (0, _react.useMemo)(() => {
    if (typeof showSizeChanger === 'boolean') {
      return [showSizeChanger, {}];
    }
    if (showSizeChanger && typeof showSizeChanger === 'object') {
      return [true, showSizeChanger];
    }
    return [undefined, undefined];
  }, [showSizeChanger]);
}