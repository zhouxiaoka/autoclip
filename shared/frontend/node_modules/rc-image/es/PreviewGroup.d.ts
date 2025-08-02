import * as React from 'react';
import type { ImgInfo, ImagePreviewType } from './Image';
import type { PreviewProps, ToolbarRenderInfoType } from './Preview';
import type { TransformType } from './hooks/useImageTransform';
import type { ImageElementProps } from './interface';
export interface PreviewGroupPreview extends Omit<ImagePreviewType, 'mask' | 'maskClassName' | 'onVisibleChange' | 'toolbarRender' | 'imageRender'> {
    /**
     * If Preview the show img index
     * @default 0
     */
    current?: number;
    countRender?: (current: number, total: number) => React.ReactNode;
    toolbarRender?: (originalNode: React.ReactElement, info: ToolbarRenderInfoType) => React.ReactNode;
    imageRender?: (originalNode: React.ReactElement, info: {
        transform: TransformType;
        current: number;
        image: ImgInfo;
    }) => React.ReactNode;
    onVisibleChange?: (value: boolean, prevValue: boolean, current: number) => void;
    onChange?: (current: number, prevCurrent: number) => void;
}
export interface GroupConsumerProps {
    previewPrefixCls?: string;
    icons?: PreviewProps['icons'];
    items?: (string | ImageElementProps)[];
    fallback?: string;
    preview?: boolean | PreviewGroupPreview;
    children?: React.ReactNode;
}
declare const Group: React.FC<GroupConsumerProps>;
export default Group;
