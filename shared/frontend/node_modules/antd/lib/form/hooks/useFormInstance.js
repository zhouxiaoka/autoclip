"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = useFormInstance;
var React = _interopRequireWildcard(require("react"));
var _context = require("../context");
function useFormInstance() {
  const {
    form
  } = React.useContext(_context.FormContext);
  return form;
}