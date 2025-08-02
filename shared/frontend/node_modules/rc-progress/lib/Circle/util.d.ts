import type { StrokeColorType } from '../interface';
import type { ProgressProps } from '..';
import type React from 'react';
export declare const VIEW_BOX_SIZE = 100;
export declare const getCircleStyle: (perimeter: number, perimeterWithoutGap: number, offset: number, percent: number, rotateDeg: number, gapDegree: number, gapPosition: ProgressProps['gapPosition'] | undefined, strokeColor: StrokeColorType, strokeLinecap: ProgressProps['strokeLinecap'], strokeWidth: number, stepSpace?: number) => React.CSSProperties;
