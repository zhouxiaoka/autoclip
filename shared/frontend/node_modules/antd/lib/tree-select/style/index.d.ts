import type { GetDefaultToken } from '../../theme/internal';
import type { TreeSharedToken } from '../../tree/style';
export interface ComponentToken extends TreeSharedToken {
}
export declare const prepareComponentToken: GetDefaultToken<'TreeSelect'>;
export default function useTreeSelectStyle(prefixCls: string, treePrefixCls: string, rootCls: string): readonly [(node: React.ReactElement) => React.ReactElement, string, string];
