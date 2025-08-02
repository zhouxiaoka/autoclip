export function getPlacementStyle(placement, top, bottom) {
  let style;
  switch (placement) {
    case 'top':
      style = {
        left: '50%',
        transform: 'translateX(-50%)',
        right: 'auto',
        top,
        bottom: 'auto'
      };
      break;
    case 'topLeft':
      style = {
        left: 0,
        top,
        bottom: 'auto'
      };
      break;
    case 'topRight':
      style = {
        right: 0,
        top,
        bottom: 'auto'
      };
      break;
    case 'bottom':
      style = {
        left: '50%',
        transform: 'translateX(-50%)',
        right: 'auto',
        top: 'auto',
        bottom
      };
      break;
    case 'bottomLeft':
      style = {
        left: 0,
        top: 'auto',
        bottom
      };
      break;
    default:
      style = {
        right: 0,
        top: 'auto',
        bottom
      };
      break;
  }
  return style;
}
export function getMotion(prefixCls) {
  return {
    motionName: `${prefixCls}-fade`
  };
}
export function getCloseIconConfig(closeIcon, notificationConfig, notification) {
  if (typeof closeIcon !== 'undefined') {
    return closeIcon;
  }
  if (typeof (notificationConfig === null || notificationConfig === void 0 ? void 0 : notificationConfig.closeIcon) !== 'undefined') {
    return notificationConfig.closeIcon;
  }
  return notification === null || notification === void 0 ? void 0 : notification.closeIcon;
}