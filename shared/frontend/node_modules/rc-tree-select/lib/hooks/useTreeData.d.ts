import * as React from 'react';
import type { DataNode, SimpleModeConfig } from '../interface';
/**
 * 将 `treeData` 或 `children` 转换为格式化的 `treeData`。
 * 如果 `treeData` 或 `children` 没有变化，则不会重新计算。
 */
export default function useTreeData(treeData: DataNode[], children: React.ReactNode, simpleMode: boolean | SimpleModeConfig): DataNode[];
