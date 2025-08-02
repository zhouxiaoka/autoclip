import _typeof from "@babel/runtime/helpers/esm/typeof";
import rules from "../rule";
var required = function required(rule, value, callback, source, options) {
  var errors = [];
  var type = Array.isArray(value) ? 'array' : _typeof(value);
  rules.required(rule, value, source, errors, options, type);
  callback(errors);
};
export default required;