import type { CSSProperties } from 'react';
import type { FullToken, GenerateStyle, GetDefaultToken } from '../../theme/internal';
/** Component only token. Which will handle additional calculation of alias token */
export interface ComponentToken {
    /**
     * @desc 折叠面板头部内边距
     * @descEN Padding of header
     */
    headerPadding: CSSProperties['padding'];
    /**
     * @desc 折叠面板头部背景
     * @descEN Background of header
     */
    headerBg: string;
    /**
     * @desc 折叠面板内容内边距
     * @descEN Padding of content
     */
    contentPadding: CSSProperties['padding'];
    /**
     * @desc 折叠面板内容背景
     * @descEN Background of content
     */
    contentBg: string;
    /**
     * @desc 简约风格折叠面板的内容内边距
     * @descEN Padding of content in borderless style
     */
    borderlessContentPadding: CSSProperties['padding'];
    /**
     * @desc 简约风格折叠面板的内容背景
     * @descEN Background of content in borderless style
     */
    borderlessContentBg: string;
}
type CollapseToken = FullToken<'Collapse'> & {
    /**
     * @desc 小号折叠面板头部内边距
     * @descEN Padding of small header
     */
    collapseHeaderPaddingSM: string;
    /**
     * @desc 大号折叠面板头部内边距
     * @descEN Padding of large header
     */
    collapseHeaderPaddingLG: string;
    /**
     * @desc 折叠面板边框圆角
     * @descEN Border radius of collapse panel
     */
    collapsePanelBorderRadius: number;
};
export declare const genBaseStyle: GenerateStyle<CollapseToken>;
export declare const prepareComponentToken: GetDefaultToken<'Collapse'>;
declare const _default: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export default _default;
