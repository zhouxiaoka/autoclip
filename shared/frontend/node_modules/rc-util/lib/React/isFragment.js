"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = isFragment;
var _typeof2 = _interopRequireDefault(require("@babel/runtime/helpers/typeof"));
var REACT_ELEMENT_TYPE_18 = Symbol.for('react.element');
var REACT_ELEMENT_TYPE_19 = Symbol.for('react.transitional.element');
var REACT_FRAGMENT_TYPE = Symbol.for('react.fragment');

/**
 * Compatible with React 18 or 19 to check if node is a Fragment.
 */
function isFragment(object) {
  return (
    // Base object type
    object && (0, _typeof2.default)(object) === 'object' && (
    // React Element type
    object.$$typeof === REACT_ELEMENT_TYPE_18 || object.$$typeof === REACT_ELEMENT_TYPE_19) &&
    // React Fragment type
    object.type === REACT_FRAGMENT_TYPE
  );
}