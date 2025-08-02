import type { AnyObject } from '../_util/type';
import type { ColumnTitle, ColumnTitleProps, ColumnType, Key } from './interface';
export declare const getColumnKey: <RecordType extends AnyObject = AnyObject>(column: ColumnType<RecordType>, defaultKey: string) => Key;
export declare function getColumnPos(index: number, pos?: string): string;
export declare const renderColumnTitle: <RecordType extends AnyObject = AnyObject>(title: ColumnTitle<RecordType>, props: ColumnTitleProps<RecordType>) => React.ReactNode;
/**
 * Safe get column title
 *
 * Should filter [object Object]
 *
 * @param title
 */
export declare const safeColumnTitle: <RecordType extends AnyObject = AnyObject>(title: ColumnTitle<RecordType>, props: ColumnTitleProps<RecordType>) => React.ReactNode;
