import { isValidElement, useMemo } from 'react';
const useTooltipProps = (tooltip, editConfigText, children) => useMemo(() => {
  if (tooltip === true) {
    return {
      title: editConfigText !== null && editConfigText !== void 0 ? editConfigText : children
    };
  }
  if (/*#__PURE__*/isValidElement(tooltip)) {
    return {
      title: tooltip
    };
  }
  if (typeof tooltip === 'object') {
    return Object.assign({
      title: editConfigText !== null && editConfigText !== void 0 ? editConfigText : children
    }, tooltip);
  }
  return {
    title: tooltip
  };
}, [tooltip, editConfigText, children]);
export default useTooltipProps;