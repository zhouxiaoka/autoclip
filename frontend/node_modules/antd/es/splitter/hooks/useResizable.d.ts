import type { ItemType } from './useItems';
export type ResizableInfo = {
    resizable: boolean;
    startCollapsible: boolean;
    endCollapsible: boolean;
};
export default function useResizable(items: ItemType[], pxSizes: number[], isRTL: boolean): ResizableInfo[];
