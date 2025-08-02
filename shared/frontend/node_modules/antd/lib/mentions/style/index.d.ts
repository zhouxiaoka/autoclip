import type { SharedComponentToken } from '../../input/style/token';
import type { GetDefaultToken } from '../../theme/internal';
export interface ComponentToken extends SharedComponentToken {
    /**
     * @desc 弹层 z-index
     * @descEN z-index of popup
     */
    zIndexPopup: number;
    /**
     * @desc 弹层高度
     * @descEN Height of popup
     */
    dropdownHeight: number | string;
    /**
     * @desc 菜单项高度
     * @descEN Height of menu item
     */
    controlItemWidth: number | string;
}
export declare const prepareComponentToken: GetDefaultToken<'Mentions'>;
declare const _default: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export default _default;
