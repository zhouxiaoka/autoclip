"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _react = require("react");
const usePrevious = value => {
  const ref = (0, _react.useRef)(undefined);
  (0, _react.useEffect)(() => {
    ref.current = value;
  });
  return ref.current;
};
var _default = exports.default = usePrevious;