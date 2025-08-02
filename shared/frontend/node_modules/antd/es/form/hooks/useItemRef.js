import * as React from 'react';
import { composeRef, getNodeRef } from "rc-util/es/ref";
import { FormContext } from '../context';
export default function useItemRef() {
  const {
    itemRef
  } = React.useContext(FormContext);
  const cacheRef = React.useRef({});
  function getRef(name, children) {
    // Outer caller already check the `supportRef`
    const childrenRef = children && typeof children === 'object' && getNodeRef(children);
    const nameStr = name.join('_');
    if (cacheRef.current.name !== nameStr || cacheRef.current.originRef !== childrenRef) {
      cacheRef.current.name = nameStr;
      cacheRef.current.originRef = childrenRef;
      cacheRef.current.ref = composeRef(itemRef(name), childrenRef);
    }
    return cacheRef.current.ref;
  }
  return getRef;
}