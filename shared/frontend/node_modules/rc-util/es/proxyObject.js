/**
 * Proxy object if environment supported
 */
export default function proxyObject(obj, extendProps) {
  if (typeof Proxy !== 'undefined' && obj) {
    return new Proxy(obj, {
      get: function get(target, prop) {
        if (extendProps[prop]) {
          return extendProps[prop];
        }

        // Proxy origin property
        var originProp = target[prop];
        return typeof originProp === 'function' ? originProp.bind(target) : originProp;
      }
    });
  }
  return obj;
}