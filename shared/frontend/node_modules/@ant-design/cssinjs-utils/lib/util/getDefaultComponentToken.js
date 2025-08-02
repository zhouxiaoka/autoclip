"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _statistic = require("./statistic");
function getDefaultComponentToken(component, token, getDefaultToken) {
  if (typeof getDefaultToken === 'function') {
    var _token$component;
    return getDefaultToken((0, _statistic.merge)(token, (_token$component = token[component]) !== null && _token$component !== void 0 ? _token$component : {}));
  }
  return getDefaultToken !== null && getDefaultToken !== void 0 ? getDefaultToken : {};
}
var _default = exports.default = getDefaultComponentToken;