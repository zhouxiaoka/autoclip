var __rest = this && this.__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
import * as React from 'react';
import toArray from "rc-util/es/Children/toArray";
function getCollapsible(collapsible) {
  if (collapsible && typeof collapsible === 'object') {
    return collapsible;
  }
  const mergedCollapsible = !!collapsible;
  return {
    start: mergedCollapsible,
    end: mergedCollapsible
  };
}
/**
 * Convert `children` into `items`.
 */
export default function useItems(children) {
  const items = React.useMemo(() => toArray(children).filter(React.isValidElement).map(node => {
    const {
      props
    } = node;
    const {
        collapsible
      } = props,
      restProps = __rest(props, ["collapsible"]);
    return Object.assign(Object.assign({}, restProps), {
      collapsible: getCollapsible(collapsible)
    });
  }), [children]);
  return items;
}