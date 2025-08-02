import type { DataEntity } from 'rc-tree/lib/interface';
import type { SafeKey, FieldNames } from '../interface';
declare const _default: (treeData: any, fieldNames: FieldNames) => {
    valueEntities: Map<SafeKey, DataEntity>;
    keyEntities: Record<string, DataEntity>;
};
export default _default;
