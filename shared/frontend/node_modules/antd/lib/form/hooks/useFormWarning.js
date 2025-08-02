"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = useFormWarning;
var React = _interopRequireWildcard(require("react"));
var _warning = require("../../_util/warning");
const names = {};
function useFormWarning({
  name
}) {
  const warning = (0, _warning.devUseWarning)('Form');
  React.useEffect(() => {
    if (name) {
      names[name] = (names[name] || 0) + 1;
      process.env.NODE_ENV !== "production" ? warning(names[name] <= 1, 'usage', 'There exist multiple Form with same `name`.') : void 0;
      return () => {
        names[name] -= 1;
      };
    }
  }, [name]);
}