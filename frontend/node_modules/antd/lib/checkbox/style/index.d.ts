import type { FullToken, GenerateStyle } from '../../theme/internal';
export interface ComponentToken {
}
/**
 * @desc Checkbox 组件的 Token
 * @descEN Token for Checkbox component
 */
interface CheckboxToken extends FullToken<'Checkbox'> {
    /**
     * @desc Checkbox 类名
     * @descEN Checkbox class name
     */
    checkboxCls: string;
    /**
     * @desc Checkbox 尺寸
     * @descEN Size of Checkbox
     */
    checkboxSize: number;
}
export declare const genCheckboxStyle: GenerateStyle<CheckboxToken>;
export declare function getStyle(prefixCls: string, token: FullToken<'Checkbox'>): import("@ant-design/cssinjs").CSSInterpolation[];
declare const _default: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export default _default;
