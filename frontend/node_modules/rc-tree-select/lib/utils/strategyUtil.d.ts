import type { DataEntity } from 'rc-tree/lib/interface';
import type { SafeKey, FieldNames } from '../interface';
export declare const SHOW_ALL = "SHOW_ALL";
export declare const SHOW_PARENT = "SHOW_PARENT";
export declare const SHOW_CHILD = "SHOW_CHILD";
export type CheckedStrategy = typeof SHOW_ALL | typeof SHOW_PARENT | typeof SHOW_CHILD;
export declare function formatStrategyValues(values: SafeKey[], strategy: CheckedStrategy, keyEntities: Record<SafeKey, DataEntity>, fieldNames: FieldNames): SafeKey[];
