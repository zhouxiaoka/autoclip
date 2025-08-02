import type { ItemType } from './useItems';
import type { ResizableInfo } from './useResizable';
/**
 * Handle user drag resize logic.
 */
export default function useResize(items: ItemType[], resizableInfos: ResizableInfo[], percentSizes: number[], containerSize: number | undefined, updateSizes: (sizes: number[]) => void, isRTL: boolean): readonly [(index: number) => void, (index: number, offset: number) => number[], () => void, (index: number, type: "start" | "end") => number[], number | undefined];
