/**
 * Proxy object if environment supported
 */
export default function proxyObject<Obj extends object, ExtendObj extends object>(obj: Obj, extendProps: ExtendObj): Obj & ExtendObj;
