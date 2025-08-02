import type { ArrowOffsetToken } from '../../style/placementArrow';
import type { ArrowToken } from '../../style/roundedArrow';
import type { FullToken, GetDefaultToken } from '../../theme/internal';
export interface ComponentToken extends ArrowToken, ArrowOffsetToken {
    /**
     * @deprecated Please use `titleMinWidth` instead
     * @desc 气泡卡片宽度
     * @descEN Width of Popover
     */
    width?: number | string;
    /**
     * @deprecated Please use `titleMinWidth` instead
     * @desc 气泡卡片最小宽度
     * @descEN Min width of Popover
     */
    minWidth?: number | string;
    /**
     * @desc 气泡卡片标题最小宽度
     * @descEN Min width of Popover title
     */
    titleMinWidth: number | string;
    /**
     * @desc 气泡卡片 z-index
     * @descEN z-index of Popover
     */
    zIndexPopup: number;
}
/**
 * @desc Popover 组件的 Token
 * @descEN Token for Popover component
 */
export type PopoverToken = FullToken<'Popover'> & {
    /**
     * @desc 气泡卡片背景色
     * @descEN Background color of Popover
     */
    popoverBg: string;
    /**
     * @desc 气泡卡片文字颜色
     * @descEN Text color of Popover
     */
    popoverColor: string;
};
export declare const prepareComponentToken: GetDefaultToken<'Popover'>;
declare const _default: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export default _default;
