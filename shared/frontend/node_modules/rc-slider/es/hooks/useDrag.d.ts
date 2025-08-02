import * as React from 'react';
import type { Direction, OnStartMove } from '../interface';
import type { OffsetValues } from './useOffset';
declare function useDrag(containerRef: React.RefObject<HTMLDivElement>, direction: Direction, rawValues: number[], min: number, max: number, formatValue: (value: number) => number, triggerChange: (values: number[]) => void, finishChange: (draggingDelete: boolean) => void, offsetValues: OffsetValues, editable: boolean, minCount: number): [
    draggingIndex: number,
    draggingValue: number,
    draggingDelete: boolean,
    returnValues: number[],
    onStartMove: OnStartMove
];
export default useDrag;
