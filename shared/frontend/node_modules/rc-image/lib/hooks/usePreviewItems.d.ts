import type { GroupConsumerProps } from '../PreviewGroup';
import type { InternalItem, RegisterImage } from '../interface';
export type Items = Omit<InternalItem, 'canPreview'>[];
/**
 * Merge props provided `items` or context collected images
 */
export default function usePreviewItems(items?: GroupConsumerProps['items']): [items: Items, registerImage: RegisterImage, fromItems: boolean];
