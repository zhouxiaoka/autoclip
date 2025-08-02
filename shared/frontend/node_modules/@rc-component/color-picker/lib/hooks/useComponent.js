"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = useComponent;
var React = _interopRequireWildcard(require("react"));
var _Slider = _interopRequireDefault(require("../components/Slider"));
function useComponent(components) {
  return React.useMemo(function () {
    var _ref = components || {},
      slider = _ref.slider;
    return [slider || _Slider.default];
  }, [components]);
}