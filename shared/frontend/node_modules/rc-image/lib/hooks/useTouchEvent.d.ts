import type React from 'react';
import type { DispatchZoomChangeFunc, TransformType, UpdateTransformFunc } from './useImageTransform';
export default function useTouchEvent(imgRef: React.MutableRefObject<HTMLImageElement>, movable: boolean, visible: boolean, minScale: number, transform: TransformType, updateTransform: UpdateTransformFunc, dispatchZoomChange: DispatchZoomChangeFunc): {
    isTouching: boolean;
    onTouchStart: (event: React.TouchEvent<HTMLImageElement>) => void;
    onTouchMove: (event: React.TouchEvent<HTMLImageElement>) => void;
    onTouchEnd: () => void;
};
