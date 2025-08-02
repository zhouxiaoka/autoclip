import * as React from 'react';
export declare function getPageXY(e: React.MouseEvent | React.TouchEvent | MouseEvent | TouchEvent, horizontal: boolean): number;
export default function useScrollDrag(inVirtual: boolean, componentRef: React.RefObject<HTMLElement>, onScrollOffset: (offset: number) => void): void;
