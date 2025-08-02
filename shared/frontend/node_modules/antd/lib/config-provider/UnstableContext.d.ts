import * as React from 'react';
export type UnmountType = () => Promise<void>;
export type RenderType = (node: React.ReactElement, container: Element | DocumentFragment) => UnmountType;
/**
 * @deprecated Set React render function for compatible usage.
 * This is internal usage only compatible with React 19.
 * And will be removed in next major version.
 */
export declare function unstableSetRender(render?: RenderType): RenderType;
