/// <reference types="react" />
import type { DataIndex, Key } from '../interface';
export interface GetColumnKeyColumn<T = any> {
    key?: Key;
    dataIndex?: DataIndex<T>;
}
export declare function getColumnsKey<T = any>(columns: readonly GetColumnKeyColumn<T>[]): import("react").Key[];
export declare function validateValue<T>(val: T): boolean;
export declare function validNumberValue(value: any): boolean;
