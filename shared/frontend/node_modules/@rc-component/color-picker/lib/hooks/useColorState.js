"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _slicedToArray2 = _interopRequireDefault(require("@babel/runtime/helpers/slicedToArray"));
var _rcUtil = require("rc-util");
var _react = require("react");
var _util = require("../util");
var useColorState = function useColorState(defaultValue, value) {
  var _useMergedState = (0, _rcUtil.useMergedState)(defaultValue, {
      value: value
    }),
    _useMergedState2 = (0, _slicedToArray2.default)(_useMergedState, 2),
    mergedValue = _useMergedState2[0],
    setValue = _useMergedState2[1];
  var color = (0, _react.useMemo)(function () {
    return (0, _util.generateColor)(mergedValue);
  }, [mergedValue]);
  return [color, setValue];
};
var _default = exports.default = useColorState;