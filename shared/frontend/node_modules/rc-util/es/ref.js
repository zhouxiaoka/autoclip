import _typeof from "@babel/runtime/helpers/esm/typeof";
import { isValidElement, version } from 'react';
import { ForwardRef, isMemo } from 'react-is';
import useMemo from "./hooks/useMemo";
import isFragment from "./React/isFragment";
var ReactMajorVersion = Number(version.split('.')[0]);
export var fillRef = function fillRef(ref, node) {
  if (typeof ref === 'function') {
    ref(node);
  } else if (_typeof(ref) === 'object' && ref && 'current' in ref) {
    ref.current = node;
  }
};

/**
 * Merge refs into one ref function to support ref passing.
 */
export var composeRef = function composeRef() {
  for (var _len = arguments.length, refs = new Array(_len), _key = 0; _key < _len; _key++) {
    refs[_key] = arguments[_key];
  }
  var refList = refs.filter(Boolean);
  if (refList.length <= 1) {
    return refList[0];
  }
  return function (node) {
    refs.forEach(function (ref) {
      fillRef(ref, node);
    });
  };
};
export var useComposeRef = function useComposeRef() {
  for (var _len2 = arguments.length, refs = new Array(_len2), _key2 = 0; _key2 < _len2; _key2++) {
    refs[_key2] = arguments[_key2];
  }
  return useMemo(function () {
    return composeRef.apply(void 0, refs);
  }, refs, function (prev, next) {
    return prev.length !== next.length || prev.every(function (ref, i) {
      return ref !== next[i];
    });
  });
};
export var supportRef = function supportRef(nodeOrComponent) {
  var _type$prototype, _nodeOrComponent$prot;
  if (!nodeOrComponent) {
    return false;
  }

  // React 19 no need `forwardRef` anymore. So just pass if is a React element.
  if (isReactElement(nodeOrComponent) && ReactMajorVersion >= 19) {
    return true;
  }
  var type = isMemo(nodeOrComponent) ? nodeOrComponent.type.type : nodeOrComponent.type;

  // Function component node
  if (typeof type === 'function' && !((_type$prototype = type.prototype) !== null && _type$prototype !== void 0 && _type$prototype.render) && type.$$typeof !== ForwardRef) {
    return false;
  }

  // Class component
  if (typeof nodeOrComponent === 'function' && !((_nodeOrComponent$prot = nodeOrComponent.prototype) !== null && _nodeOrComponent$prot !== void 0 && _nodeOrComponent$prot.render) && nodeOrComponent.$$typeof !== ForwardRef) {
    return false;
  }
  return true;
};
function isReactElement(node) {
  return /*#__PURE__*/isValidElement(node) && !isFragment(node);
}
export var supportNodeRef = function supportNodeRef(node) {
  return isReactElement(node) && supportRef(node);
};

/**
 * In React 19. `ref` is not a property from node.
 * But a property from `props.ref`.
 * To check if `props.ref` exist or fallback to `ref`.
 */
export var getNodeRef = function getNodeRef(node) {
  if (node && isReactElement(node)) {
    var ele = node;

    // Source from:
    // https://github.com/mui/material-ui/blob/master/packages/mui-utils/src/getReactNodeRef/getReactNodeRef.ts
    return ele.props.propertyIsEnumerable('ref') ? ele.props.ref : ele.ref;
  }
  return null;
};