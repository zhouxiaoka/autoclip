import type { CSSObject } from '@ant-design/cssinjs';
import type { FullToken, GenerateStyle, GetDefaultToken } from '../../theme/internal';
export interface ComponentToken {
    /**
     * @desc 预览浮层 z-index
     * @descEN z-index of preview popup
     */
    zIndexPopup: number;
    /**
     * @desc 预览操作图标大小
     * @descEN Size of preview operation icon
     */
    previewOperationSize: number;
    /**
     * @desc 预览操作图标颜色
     * @descEN Color of preview operation icon
     */
    previewOperationColor: string;
    /**
     * @desc 预览操作图标悬浮颜色
     * @descEN Color of hovered preview operation icon
     */
    previewOperationHoverColor: string;
    /**
     * @desc 预览操作图标禁用颜色
     * @descEN Disabled color of preview operation icon
     */
    previewOperationColorDisabled: string;
}
/**
 * @desc Image 组件的 Token
 * @descEN Token for Image component
 */
export interface ImageToken extends FullToken<'Image'> {
    /**
     * @desc 预览类名
     * @descEN Preview class name
     */
    previewCls: string;
    /**
     * @desc 模态框遮罩背景色
     * @descEN Background color of modal mask
     */
    modalMaskBg: string;
    /**
     * @desc 预览切换按钮尺寸
     * @descEN Size of preview switch button
     */
    imagePreviewSwitchSize: number;
}
export type PositionType = 'static' | 'relative' | 'fixed' | 'absolute' | 'sticky' | undefined;
export declare const genBoxStyle: (position?: PositionType) => CSSObject;
export declare const genImageMaskStyle: (token: ImageToken) => CSSObject;
export declare const genPreviewOperationsStyle: (token: ImageToken) => CSSObject;
export declare const genPreviewSwitchStyle: (token: ImageToken) => CSSObject;
export declare const genImagePreviewStyle: GenerateStyle<ImageToken>;
export declare const prepareComponentToken: GetDefaultToken<'Image'>;
declare const _default: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export default _default;
