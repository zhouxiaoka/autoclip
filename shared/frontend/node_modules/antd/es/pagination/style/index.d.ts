import type { SharedComponentToken, SharedInputToken } from '../../input/style/token';
import type { FullToken, GenStyleFn, GetDefaultToken } from '../../theme/internal';
export interface ComponentToken {
    /**
     * @desc 页码选项背景色
     * @descEN Background color of Pagination item
     */
    itemBg: string;
    /**
     * @desc 页码尺寸
     * @descEN Size of Pagination item
     */
    itemSize: number;
    /**
     * @desc 页码激活态背景色
     * @descEN Background color of active Pagination item
     */
    itemActiveBg: string;
    /**
     * @desc 小号页码尺寸
     * @descEN Size of small Pagination item
     */
    itemSizeSM: number;
    /**
     * @desc 页码链接背景色
     * @descEN Background color of Pagination item link
     */
    itemLinkBg: string;
    /**
     * @desc 页码激活态禁用状态背景色
     * @descEN Background color of disabled active Pagination item
     */
    itemActiveBgDisabled: string;
    /**
     * @desc 页码激活态禁用状态文字颜色
     * @descEN Text color of disabled active Pagination item
     */
    itemActiveColorDisabled: string;
    /**
     * @desc 输入框背景色
     * @descEN Background color of input
     */
    itemInputBg: string;
    /**
     * @desc 每页展示数量选择器 top
     * @descEN Top of Pagination size changer
     */
    miniOptionsSizeChangerTop: number;
}
/**
 * @desc Pagination 组件的 Token
 * @descEN Token for Pagination component
 */
export interface PaginationToken extends FullToken<'Pagination'>, SharedComponentToken, SharedInputToken {
    /**
     * @desc 输入框轮廓偏移量
     * @descEN Outline offset of input
     */
    inputOutlineOffset: number;
    /**
     * @desc 迷你选项横向外边距
     * @descEN Horizontal margin of mini options
     */
    paginationMiniOptionsMarginInlineStart: number | string;
    /**
     * @desc 迷你快速跳转输入框宽度
     * @descEN Width of mini quick jumper input
     */
    paginationMiniQuickJumperInputWidth: number | string;
    /**
     * @desc 页码横向内边距
     * @descEN Horizontal padding of Pagination item
     */
    paginationItemPaddingInline: number | string;
    /**
     * @desc 省略号字母间距
     * @descEN Letter spacing of ellipsis
     */
    paginationEllipsisLetterSpacing: number | string;
    /**
     * @desc 省略号文本缩进
     * @descEN Text indent of ellipsis
     */
    paginationEllipsisTextIndent: string;
    /**
     * @desc 斜杠横向外边距
     * @descEN Horizontal margin of slash
     */
    paginationSlashMarginInlineStart: number;
    /**
     * @desc 斜杠横向外边距
     * @descEN Horizontal margin of slash
     */
    paginationSlashMarginInlineEnd: number;
}
export declare const prepareComponentToken: GetDefaultToken<'Pagination'>;
export declare const prepareToken: (token: Parameters<GenStyleFn<"Pagination">>[0]) => PaginationToken;
declare const _default: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export default _default;
