import type { TransferProps } from '..';
import type { AnyObject } from '../../_util/type';
import type { TransferKey } from '../interface';
declare const useData: <RecordType extends AnyObject>(dataSource?: RecordType[], rowKey?: TransferProps<RecordType>["rowKey"], targetKeys?: TransferKey[]) => RecordType[][];
export default useData;
