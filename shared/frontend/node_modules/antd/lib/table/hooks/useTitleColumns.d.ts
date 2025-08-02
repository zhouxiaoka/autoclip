import type { AnyObject } from 'antd/es/_util/type';
import type { ColumnTitleProps, TransformColumns } from '../interface';
declare const useTitleColumns: <RecordType extends AnyObject = AnyObject>(columnTitleProps: ColumnTitleProps<RecordType>) => readonly [TransformColumns<RecordType>];
export default useTitleColumns;
