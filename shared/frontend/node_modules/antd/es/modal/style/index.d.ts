import type React from 'react';
import type { AliasToken, FullToken, GenerateStyle, GenStyleFn, GlobalToken, TokenWithCommonCls } from '../../theme/internal';
/** Component only token. Which will handle additional calculation of alias token */
export interface ComponentToken {
    /**
     * @desc 顶部背景色
     * @descEN Background color of header
     */
    headerBg: string;
    /**
     * @desc 标题行高
     * @descEN Line height of title
     */
    titleLineHeight: number | string;
    /**
     * @desc 标题字体大小
     * @descEN Font size of title
     */
    titleFontSize: number;
    /**
     * @desc 标题字体颜色
     * @descEN Font color of title
     */
    titleColor: string;
    /**
     * @desc 内容区域背景色
     * @descEN Background color of content
     */
    contentBg: string;
    /**
     * @desc 底部区域背景色
     * @descEN Background color of footer
     */
    footerBg: string;
}
/**
 * @desc Modal 组件的 Token
 * @descEN Token for Modal component
 */
export interface ModalToken extends FullToken<'Modal'> {
    /**
     * @desc 模态框头部高度
     * @descEN Height of modal header
     */
    modalHeaderHeight: number | string;
    /**
     * @desc 模态框底部边框颜色
     * @descEN Border color of modal footer
     */
    modalFooterBorderColorSplit: string;
    /**
     * @desc 模态框底部边框样式
     * @descEN Border style of modal footer
     */
    modalFooterBorderStyle: string;
    /**
     * @desc 模态框底部边框宽度
     * @descEN Border width of modal footer
     */
    modalFooterBorderWidth: number | string;
    /**
     * @desc 模态框关闭图标颜色
     * @descEN Color of modal close icon
     */
    modalCloseIconColor: string;
    /**
     * @desc 模态框关闭图标悬停颜色
     * @descEN Hover color of modal close icon
     */
    modalCloseIconHoverColor: string;
    /**
     * @desc 模态框关闭按钮尺寸
     * @descEN Size of modal close button
     */
    modalCloseBtnSize: number | string;
    /**
     * @desc 模态框确认图标尺寸
     * @descEN Size of modal confirm icon
     */
    modalConfirmIconSize: number | string;
    /**
     * @desc 模态框标题高度
     * @descEN Height of modal title
     */
    modalTitleHeight: number | string;
}
export declare const genModalMaskStyle: GenerateStyle<TokenWithCommonCls<AliasToken>>;
export declare const prepareToken: (token: Parameters<GenStyleFn<'Modal'>>[0]) => ModalToken;
export declare const prepareComponentToken: (token: GlobalToken) => {
    footerBg: string;
    headerBg: string;
    titleLineHeight: number;
    titleFontSize: number;
    contentBg: string;
    titleColor: string;
    contentPadding: string | number;
    headerPadding: string | number;
    headerBorderBottom: string;
    headerMarginBottom: number;
    bodyPadding: number;
    footerPadding: string | number;
    footerBorderTop: string;
    footerBorderRadius: string | number;
    footerMarginTop: number;
    confirmBodyPadding: string | number;
    confirmIconMarginInlineEnd: number;
    confirmBtnsMarginTop: number;
};
declare const _default: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export default _default;
