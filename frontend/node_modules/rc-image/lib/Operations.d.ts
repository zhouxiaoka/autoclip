import * as React from 'react';
import type { ImgInfo } from './Image';
import type { PreviewProps, ToolbarRenderInfoType } from './Preview';
import type { TransformType } from './hooks/useImageTransform';
interface OperationsProps extends Pick<PreviewProps, 'visible' | 'maskTransitionName' | 'getContainer' | 'prefixCls' | 'rootClassName' | 'icons' | 'countRender' | 'closeIcon' | 'onClose'> {
    showSwitch: boolean;
    showProgress: boolean;
    current: number;
    transform: TransformType;
    count: number;
    scale: number;
    minScale: number;
    maxScale: number;
    onActive: (offset: number) => void;
    onZoomIn: () => void;
    onZoomOut: () => void;
    onRotateRight: () => void;
    onRotateLeft: () => void;
    onFlipX: () => void;
    onFlipY: () => void;
    onReset: () => void;
    toolbarRender: (originalNode: React.ReactElement, info: ToolbarRenderInfoType | Omit<ToolbarRenderInfoType, 'current' | 'total'>) => React.ReactNode;
    zIndex?: number;
    image?: ImgInfo;
}
declare const Operations: React.FC<OperationsProps>;
export default Operations;
