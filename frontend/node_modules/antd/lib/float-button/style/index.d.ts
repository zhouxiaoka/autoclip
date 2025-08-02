import type { FullToken, GetDefaultToken } from '../../theme/internal';
/** Component only token. Which will handle additional calculation of alias token */
export interface ComponentToken {
}
/**
 * @desc FloatButton 组件的 Token
 * @descEN Token for FloatButton component
 */
export type FloatButtonToken = FullToken<'FloatButton'> & {
    /**
     * @desc FloatButton 颜色
     * @descEN Color of FloatButton
     */
    floatButtonColor: string;
    /**
     * @desc FloatButton 背景颜色
     * @descEN Background color of FloatButton
     */
    floatButtonBackgroundColor: string;
    /**
     * @desc FloatButton 悬停背景颜色
     * @descEN Hover background color of FloatButton
     */
    floatButtonHoverBackgroundColor: string;
    /**
     * @desc FloatButton 字体大小
     * @descEN Font size of FloatButton
     */
    floatButtonFontSize: number;
    /**
     * @desc FloatButton 尺寸
     * @descEN Size of FloatButton
     */
    floatButtonSize: number;
    /**
     * @desc FloatButton 图标尺寸
     * @descEN Icon size of FloatButton
     */
    floatButtonIconSize: number | string;
    /**
     * @desc FloatButton 主体尺寸
     * @descEN Body size of FloatButton
     */
    floatButtonBodySize: number | string;
    /**
     * @desc FloatButton 主体内间距
     * @descEN Body padding of FloatButton
     */
    floatButtonBodyPadding: number;
    /**
     * @desc 徽标偏移量
     * @descEN Offset of badge
     */
    badgeOffset: number | string;
    /**
     * @desc FloatButton 底部内边距
     * @descEN Bottom inset of FloatButton
     */
    floatButtonInsetBlockEnd: number;
    /**
     * @desc FloatButton 右侧内边距
     * @descEN Right inset of FloatButton
     */
    floatButtonInsetInlineEnd: number;
};
export declare const prepareComponentToken: GetDefaultToken<'FloatButton'>;
declare const _default: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export default _default;
