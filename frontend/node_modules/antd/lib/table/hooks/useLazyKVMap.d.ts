import type { AnyObject } from '../../_util/type';
import type { GetRowKey, Key } from '../interface';
declare const useLazyKVMap: <RecordType extends AnyObject = AnyObject>(data: readonly RecordType[], childrenColumnName: string, getRowKey: GetRowKey<RecordType>) => readonly [(key: Key) => RecordType];
export default useLazyKVMap;
