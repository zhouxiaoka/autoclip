import * as React from 'react';
import type { RenderExpandIconProps, Key, GetRowKey, ExpandableConfig } from '../interface';
export declare function renderExpandIcon<RecordType>({ prefixCls, record, onExpand, expanded, expandable, }: RenderExpandIconProps<RecordType>): React.JSX.Element;
export declare function findAllChildrenKeys<RecordType>(data: readonly RecordType[], getRowKey: GetRowKey<RecordType>, childrenColumnName: string): Key[];
export declare function computedExpandedClassName<RecordType>(cls: ExpandableConfig<RecordType>['expandedRowClassName'], record: RecordType, index: number, indent: number): string;
