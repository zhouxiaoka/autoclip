import * as React from 'react';
import type { ExpandAction } from 'rc-tree/lib/Tree';
import type { DataNode, FieldNames, Key } from './interface';
import type useDataEntities from './hooks/useDataEntities';
export interface TreeSelectContextProps {
    virtual?: boolean;
    dropdownMatchSelectWidth?: boolean | number;
    listHeight: number;
    listItemHeight: number;
    listItemScrollOffset?: number;
    treeData: DataNode[];
    fieldNames: FieldNames;
    onSelect: (value: Key, info: {
        selected: boolean;
    }) => void;
    treeExpandAction?: ExpandAction;
    treeTitleRender?: (node: any) => React.ReactNode;
    onPopupScroll?: React.UIEventHandler<HTMLDivElement>;
    leftMaxCount: number | null;
    /** When `true`, only take leaf node as count, or take all as count with `maxCount` limitation */
    leafCountOnly: boolean;
    valueEntities: ReturnType<typeof useDataEntities>['valueEntities'];
}
declare const TreeSelectContext: React.Context<TreeSelectContextProps>;
export default TreeSelectContext;
