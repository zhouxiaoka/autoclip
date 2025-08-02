"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = useRootProps;
var React = _interopRequireWildcard(require("react"));
var _miscUtil = require("../../../utils/miscUtil");
var propNames = ['onMouseEnter', 'onMouseLeave'];
function useRootProps(props) {
  return React.useMemo(function () {
    return (0, _miscUtil.pickProps)(props, propNames);
  }, [props]);
}