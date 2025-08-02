import { isValidElement } from 'react';
function convertToTooltipProps(tooltip) {
  // isNil
  if (tooltip === undefined || tooltip === null) {
    return null;
  }
  if (typeof tooltip === 'object' && ! /*#__PURE__*/isValidElement(tooltip)) {
    return tooltip;
  }
  return {
    title: tooltip
  };
}
export default convertToTooltipProps;