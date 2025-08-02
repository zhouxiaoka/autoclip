import type * as React from 'react';
export default function useMobileTouchMove(inVirtual: boolean, listRef: React.RefObject<HTMLDivElement>, callback: (isHorizontal: boolean, offset: number, smoothOffset: boolean, e?: TouchEvent) => boolean): void;
