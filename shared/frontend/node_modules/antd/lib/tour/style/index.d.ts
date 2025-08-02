import type { ArrowOffsetToken } from '../../style/placementArrow';
import type { ArrowToken } from '../../style/roundedArrow';
import type { GetDefaultToken } from '../../theme/internal';
export interface ComponentToken extends ArrowOffsetToken, ArrowToken {
    /**
     * @desc 弹层 z-index
     * @descEN Tour popup z-index
     */
    zIndexPopup: number;
    /**
     * @desc 关闭按钮尺寸
     * @descEN Close button size
     */
    closeBtnSize: number;
    /**
     * @desc Primary 模式上一步按钮背景色
     * @descEN Background color of previous button in primary type
     */
    primaryPrevBtnBg: string;
    /**
     * @desc Primary 模式下一步按钮悬浮背景色
     * @descEN Hover background color of next button in primary type
     */
    primaryNextBtnHoverBg: string;
}
export declare const prepareComponentToken: GetDefaultToken<'Tour'>;
declare const _default: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export default _default;
