import * as React from 'react';
import useRowInfo from '../hooks/useRowInfo';
import type { ColumnType, CustomizeComponent } from '../interface';
export interface BodyRowProps<RecordType> {
    record: RecordType;
    index: number;
    renderIndex: number;
    className?: string;
    style?: React.CSSProperties;
    rowComponent: CustomizeComponent;
    cellComponent: CustomizeComponent;
    scopeCellComponent: CustomizeComponent;
    indent?: number;
    rowKey: React.Key;
    rowKeys: React.Key[];
    expandedRowInfo?: {
        offset: number;
        colSpan: number;
        sticky: number;
    };
}
export declare function getCellProps<RecordType>(rowInfo: ReturnType<typeof useRowInfo<RecordType>>, column: ColumnType<RecordType>, colIndex: number, indent: number, index: number, rowKeys?: React.Key[], expandedRowOffset?: number): {
    key: React.Key;
    fixedInfo: import("../utils/fixUtil").FixedInfo;
    appendCellNode: React.ReactNode;
    additionalCellProps: React.HTMLAttributes<any> & React.TdHTMLAttributes<any>;
};
declare function BodyRow<RecordType extends {
    children?: readonly RecordType[];
}>(props: BodyRowProps<RecordType>): React.JSX.Element;
declare namespace BodyRow {
    var displayName: string;
}
declare const _default: typeof BodyRow;
export default _default;
