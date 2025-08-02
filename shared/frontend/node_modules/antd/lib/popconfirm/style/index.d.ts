import type { FullToken, GetDefaultToken } from '../../theme/internal';
export interface ComponentToken {
    /**
     * @desc 确认框 z-index
     * @descEN z-index of Popconfirm
     */
    zIndexPopup: number;
}
/**
 * @desc Popconfirm 组件的 Token
 * @descEN Token for Popconfirm component
 */
export interface PopconfirmToken extends FullToken<'Popconfirm'> {
}
export declare const prepareComponentToken: GetDefaultToken<'Popconfirm'>;
declare const _default: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export default _default;
