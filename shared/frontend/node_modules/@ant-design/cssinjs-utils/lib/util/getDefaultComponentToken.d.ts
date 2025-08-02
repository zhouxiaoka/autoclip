import type { TokenType } from '@ant-design/cssinjs';
import type { GetDefaultToken } from './genStyleUtils';
import type { GlobalToken, TokenMap, TokenMapKey } from '../interface';
declare function getDefaultComponentToken<CompTokenMap extends TokenMap, AliasToken extends TokenType, C extends TokenMapKey<CompTokenMap>>(component: C, token: GlobalToken<CompTokenMap, AliasToken>, getDefaultToken: GetDefaultToken<CompTokenMap, AliasToken, C>): any;
export default getDefaultComponentToken;
