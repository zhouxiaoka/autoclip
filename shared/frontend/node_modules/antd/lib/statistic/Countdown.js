"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var React = _interopRequireWildcard(require("react"));
var _warning = require("../_util/warning");
var _Timer = _interopRequireDefault(require("./Timer"));
const Countdown = props => {
  if (process.env.NODE_ENV !== 'production') {
    const warning = (0, _warning.devUseWarning)('Countdown');
    warning.deprecated(false, '<Statistic.Countdown />', '<Statistic.Timer type="countdown" />');
  }
  return /*#__PURE__*/React.createElement(_Timer.default, Object.assign({}, props, {
    type: "countdown"
  }));
};
var _default = exports.default = /*#__PURE__*/React.memo(Countdown);