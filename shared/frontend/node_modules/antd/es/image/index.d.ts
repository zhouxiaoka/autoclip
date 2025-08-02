import * as React from 'react';
import type { ImagePreviewType, ImageProps as RcImageProps } from 'rc-image';
import PreviewGroup from './PreviewGroup';
export interface CompositionImage<P> extends React.FC<P> {
    PreviewGroup: typeof PreviewGroup;
}
type Replace<T, K extends keyof T, V> = Partial<Omit<T, K> & {
    [P in K]: V;
}>;
interface PreviewType extends Omit<ImagePreviewType, 'destroyOnClose'> {
    /** @deprecated Please use destroyOnHidden instead */
    destroyOnClose?: boolean;
    /**
     * @since 5.25.0
     */
    destroyOnHidden?: boolean;
}
type ImageProps = Replace<RcImageProps, 'preview', boolean | PreviewType>;
declare const Image: CompositionImage<ImageProps>;
export type { ImageProps };
export default Image;
