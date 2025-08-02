import type { CSSProperties } from 'react';
import type { FullToken, GenStyleFn, GetDefaultToken } from '../../theme/internal';
export interface ComponentToken {
    /**
     * @desc 必填项标记颜色
     * @descEN Required mark color
     */
    labelRequiredMarkColor: string;
    /**
     * @desc 标签颜色
     * @descEN Label color
     */
    labelColor: string;
    /**
     * @desc 标签字体大小
     * @descEN Label font size
     */
    labelFontSize: number;
    /**
     * @desc 标签高度
     * @descEN Label height
     */
    labelHeight: number | string;
    /**
     * @desc 标签冒号前间距
     * @descEN Label colon margin-inline-start
     */
    labelColonMarginInlineStart: number;
    /**
     * @desc 标签冒号后间距
     * @descEN Label colon margin-inline-end
     */
    labelColonMarginInlineEnd: number;
    /**
     * @desc 表单项间距
     * @descEN Form item margin bottom
     */
    itemMarginBottom: number;
    /**
     * @desc 行内布局表单项间距
     * @descEN Inline layout form item margin bottom
     */
    inlineItemMarginBottom: number;
    /**
     * @desc 垂直布局标签内边距
     * @descEN Vertical layout label padding
     */
    verticalLabelPadding: CSSProperties['padding'];
    /**
     * @desc 垂直布局标签外边距
     * @descEN Vertical layout label margin
     */
    verticalLabelMargin: CSSProperties['margin'];
}
/**
 * @desc Form 组件的 Token
 * @descEN Token for Form component
 */
export interface FormToken extends FullToken<'Form'> {
    /**
     * @desc 表单项类名
     * @descEN Form item class name
     */
    formItemCls: string;
    /**
     * @desc 根前缀类名
     * @descEN Root prefix class name
     */
    rootPrefixCls: string;
}
export declare const prepareComponentToken: GetDefaultToken<'Form'>;
export declare const prepareToken: (token: Parameters<GenStyleFn<'Form'>>[0], rootPrefixCls: string) => FormToken;
declare const _default: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export default _default;
