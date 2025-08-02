"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = useItemRef;
var React = _interopRequireWildcard(require("react"));
var _ref = require("rc-util/lib/ref");
var _context = require("../context");
function useItemRef() {
  const {
    itemRef
  } = React.useContext(_context.FormContext);
  const cacheRef = React.useRef({});
  function getRef(name, children) {
    // Outer caller already check the `supportRef`
    const childrenRef = children && typeof children === 'object' && (0, _ref.getNodeRef)(children);
    const nameStr = name.join('_');
    if (cacheRef.current.name !== nameStr || cacheRef.current.originRef !== childrenRef) {
      cacheRef.current.name = nameStr;
      cacheRef.current.originRef = childrenRef;
      cacheRef.current.ref = (0, _ref.composeRef)(itemRef(name), childrenRef);
    }
    return cacheRef.current.ref;
  }
  return getRef;
}