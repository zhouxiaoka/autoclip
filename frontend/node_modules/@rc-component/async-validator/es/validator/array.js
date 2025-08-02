import rules from "../rule/index";
var array = function array(rule, value, callback, source, options) {
  var errors = [];
  var validate = rule.required || !rule.required && source.hasOwnProperty(rule.field);
  if (validate) {
    if ((value === undefined || value === null) && !rule.required) {
      return callback();
    }
    rules.required(rule, value, source, errors, options, 'array');
    if (value !== undefined && value !== null) {
      rules.type(rule, value, source, errors, options);
      rules.range(rule, value, source, errors, options);
    }
  }
  callback(errors);
};
export default array;