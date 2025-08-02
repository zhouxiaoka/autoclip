import type { CSSProperties } from 'react';
import type { ArrowOffsetToken } from '../../style/placementArrow';
import type { ArrowToken } from '../../style/roundedArrow';
import type { FullToken, GetDefaultToken } from '../../theme/internal';
export interface ComponentToken extends ArrowToken, ArrowOffsetToken {
    /**
     * @desc 下拉菜单 z-index
     * @descEN z-index of dropdown
     */
    zIndexPopup: number;
    /**
     * @desc 下拉菜单纵向内边距
     * @descEN Vertical padding of dropdown
     */
    paddingBlock: CSSProperties['paddingBlock'];
}
/**
 * @desc Dropdown 组件的 Token
 * @descEN Token for Dropdown component
 */
export interface DropdownToken extends FullToken<'Dropdown'> {
    /**
     * @desc 下拉箭头距离
     * @descEN Distance of dropdown arrow
     */
    dropdownArrowDistance: number | string;
    /**
     * @desc 下拉菜单边缘子项内边距
     * @descEN Padding of edge child in dropdown menu
     */
    dropdownEdgeChildPadding: number;
    /**
     * @desc 菜单类名
     * @descEN Menu class name
     */
    menuCls: string;
}
export declare const prepareComponentToken: GetDefaultToken<'Dropdown'>;
declare const _default: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export default _default;
