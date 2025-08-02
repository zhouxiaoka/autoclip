import type { GetDefaultToken } from '../../theme/internal';
/** Component only token. Which will handle additional calculation of alias token */
export interface ComponentToken {
    /**
     * @desc 弹出层的 z-index
     * @descEN z-index of popup
     */
    zIndexPopup: number;
}
export declare const prepareComponentToken: GetDefaultToken<'BackTop'>;
declare const _default: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export default _default;
