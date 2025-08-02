import type { TokenMap, TokenMapKey, ComponentTokenKey, GlobalToken } from '../interface';
import type { TokenType } from '@ant-design/cssinjs';
declare function getComponentToken<CompTokenMap extends TokenMap, AliasToken extends TokenType, C extends TokenMapKey<CompTokenMap>>(component: C, token: GlobalToken<CompTokenMap, AliasToken>, defaultToken: CompTokenMap[C], options?: {
    deprecatedTokens?: [
        ComponentTokenKey<CompTokenMap, AliasToken, C>,
        ComponentTokenKey<CompTokenMap, AliasToken, C>
    ][];
}): any;
export default getComponentToken;
