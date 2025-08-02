import type { CSSProperties } from 'react';
import type { FullToken, GenStyleFn, GetDefaultToken, PresetColorKey } from '../../theme/internal';
/** Component only token. Which will handle additional calculation of alias token */
export interface ComponentToken {
    /**
     * @desc 文字字重
     * @descEN Font weight of text
     */
    fontWeight: CSSProperties['fontWeight'];
    /**
     * @desc 默认按钮阴影
     * @descEN Shadow of default button
     */
    defaultShadow: string;
    /**
     * @desc 主要按钮阴影
     * @descEN Shadow of primary button
     */
    primaryShadow: string;
    /**
     * @desc 危险按钮阴影
     * @descEN Shadow of danger button
     */
    dangerShadow: string;
    /**
     * @desc 主要按钮文本颜色
     * @descEN Text color of primary button
     */
    primaryColor: string;
    /**
     * @desc 默认按钮文本颜色
     * @descEN Text color of default button
     */
    defaultColor: string;
    /**
     * @desc 默认按钮背景色
     * @descEN Background color of default button
     */
    defaultBg: string;
    /**
     * @desc 默认按钮边框颜色
     * @descEN Border color of default button
     */
    defaultBorderColor: string;
    /**
     * @desc 危险按钮文本颜色
     * @descEN Text color of danger button
     */
    dangerColor: string;
    /**
     * @desc 默认按钮悬浮态背景色
     * @descEN Background color of default button when hover
     */
    defaultHoverBg: string;
    /**
     * @desc 默认按钮悬浮态文本颜色
     * @descEN Text color of default button when hover
     */
    defaultHoverColor: string;
    /**
     * @desc 默认按钮悬浮态边框颜色
     * @descEN Border color of default button
     */
    defaultHoverBorderColor: string;
    /**
     * @desc 默认按钮激活态背景色
     * @descEN Background color of default button when active
     */
    defaultActiveBg: string;
    /**
     * @desc 默认按钮激活态文字颜色
     * @descEN Text color of default button when active
     */
    defaultActiveColor: string;
    /**
     * @desc 默认按钮激活态边框颜色
     * @descEN Border color of default button when active
     */
    defaultActiveBorderColor: string;
    /**
     * @desc 禁用状态边框颜色
     * @descEN Border color of disabled button
     */
    borderColorDisabled: string;
    /**
     * @desc 默认幽灵按钮文本颜色
     * @descEN Text color of default ghost button
     */
    defaultGhostColor: string;
    /**
     * @desc 幽灵按钮背景色
     * @descEN Background color of ghost button
     */
    ghostBg: string;
    /**
     * @desc 默认幽灵按钮边框颜色
     * @descEN Border color of default ghost button
     */
    defaultGhostBorderColor: string;
    /**
     * @desc 主要填充按钮的浅色背景颜色
     * @descEN Background color of primary filled button
     */
    /**
     * @desc 默认实心按钮的文本色
     * @descEN Default text color for solid buttons.
     */
    solidTextColor: string;
    /**
     * @desc 默认文本按钮的文本色
     * @descEN Default text color for text buttons
     */
    textTextColor: string;
    /**
     * @desc 默认文本按钮悬浮态文本颜色
     * @descEN Default text color for text buttons on hover
     */
    textTextHoverColor: string;
    /**
     * @desc 默认文本按钮激活态文字颜色
     * @descEN Default text color for text buttons on active
     */
    textTextActiveColor: string;
    /**
     * @desc 按钮横向内间距
     * @descEN Horizontal padding of button
     */
    paddingInline: CSSProperties['paddingInline'];
    /**
     * @desc 大号按钮横向内间距
     * @descEN Horizontal padding of large button
     */
    paddingInlineLG: CSSProperties['paddingInline'];
    /**
     * @desc 小号按钮横向内间距
     * @descEN Horizontal padding of small button
     */
    paddingInlineSM: CSSProperties['paddingInline'];
    /**
     * @desc 按钮纵向内间距
     * @descEN Vertical padding of button
     */
    paddingBlock: CSSProperties['paddingBlock'];
    /**
     * @desc 大号按钮纵向内间距
     * @descEN Vertical padding of large button
     */
    paddingBlockLG: CSSProperties['paddingBlock'];
    /**
     * @desc 小号按钮纵向内间距
     * @descEN Vertical padding of small button
     */
    paddingBlockSM: CSSProperties['paddingBlock'];
    /**
     * @desc 只有图标的按钮图标尺寸
     * @descEN Icon size of button which only contains icon
     */
    onlyIconSize: number | string;
    /**
     * @desc 大号只有图标的按钮图标尺寸
     * @descEN Icon size of large button which only contains icon
     */
    onlyIconSizeLG: number | string;
    /**
     * @desc 小号只有图标的按钮图标尺寸
     * @descEN Icon size of small button which only contains icon
     */
    onlyIconSizeSM: number | string;
    /**
     * @desc 按钮组边框颜色
     * @descEN Border color of button group
     */
    groupBorderColor: string;
    /**
     * @desc 链接按钮悬浮态背景色
     * @descEN Background color of link button when hover
     */
    linkHoverBg: string;
    /**
     * @desc 文本按钮悬浮态背景色
     * @descEN Background color of text button when hover
     */
    textHoverBg: string;
    /**
     * @desc 按钮内容字体大小
     * @descEN Font size of button content
     */
    contentFontSize: number;
    /**
     * @desc 大号按钮内容字体大小
     * @descEN Font size of large button content
     */
    contentFontSizeLG: number;
    /**
     * @desc 小号按钮内容字体大小
     * @descEN Font size of small button content
     */
    contentFontSizeSM: number;
    /**
     * @desc 按钮内容字体行高
     * @descEN Line height of button content
     */
    contentLineHeight: number;
    /**
     * @desc 大号按钮内容字体行高
     * @descEN Line height of large button content
     */
    contentLineHeightLG: number;
    /**
     * @desc 小号按钮内容字体行高
     * @descEN Line height of small button content
     */
    contentLineHeightSM: number;
}
type ShadowColorMap = {
    [Key in `${PresetColorKey}ShadowColor`]: string;
};
export interface ButtonToken extends FullToken<'Button'>, ShadowColorMap {
    /**
     * @desc 按钮横向内边距
     * @descEN Horizontal padding of button
     */
    buttonPaddingHorizontal: CSSProperties['paddingInline'];
    /**
     * @desc 按钮纵向内边距
     * @descEN Vertical padding of button
     */
    buttonPaddingVertical: CSSProperties['paddingBlock'];
    /**
     * @desc 只有图标的按钮图标尺寸
     * @descEN Icon size of button which only contains icon
     */
    buttonIconOnlyFontSize: number | string;
}
export declare const prepareToken: (token: Parameters<GenStyleFn<'Button'>>[0]) => ButtonToken;
export declare const prepareComponentToken: GetDefaultToken<'Button'>;
export {};
