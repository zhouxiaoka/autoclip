export type ZIndexContainer = 'Modal' | 'Drawer' | 'Popover' | 'Popconfirm' | 'Tooltip' | 'Tour' | 'FloatButton';
export type ZIndexConsumer = 'SelectLike' | 'Dropdown' | 'DatePicker' | 'Menu' | 'ImagePreview';
export declare const CONTAINER_MAX_OFFSET: number;
export declare const containerBaseZIndexOffset: Record<ZIndexContainer, number>;
export declare const consumerBaseZIndexOffset: Record<ZIndexConsumer, number>;
type ReturnResult = [zIndex: number | undefined, contextZIndex: number];
export declare const useZIndex: (componentType: ZIndexContainer | ZIndexConsumer, customZIndex?: number) => ReturnResult;
export {};
