import type { TransferKey } from '../transfer/interface';
export declare const groupKeysMap: (keys: TransferKey[]) => Map<React.Key, number>;
export declare const groupDisabledKeysMap: <RecordType extends any[]>(dataSource: RecordType) => Map<React.Key, number>;
