import type { TreeSelectProps } from '../TreeSelect';
import type { DataNode, FieldNames } from '../interface';
declare const useFilterTreeData: (treeData: DataNode[], searchValue: string, options: {
    fieldNames: FieldNames;
    treeNodeFilterProp: string;
    filterTreeNode: TreeSelectProps['filterTreeNode'];
}) => DataNode[];
export default useFilterTreeData;
