import type { DataNode, FieldNames, SafeKey } from '../interface';
export declare const toArray: <T>(value: T | T[]) => T[];
export declare const fillFieldNames: (fieldNames?: FieldNames) => {
    _title: string[];
    value: string;
    key: string;
    children: string;
};
export declare const isCheckDisabled: (node: DataNode) => boolean;
export declare const getAllKeys: (treeData: DataNode[], fieldNames: FieldNames) => SafeKey[];
export declare const isNil: (val: any) => boolean;
