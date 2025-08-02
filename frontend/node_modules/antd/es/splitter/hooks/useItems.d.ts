import * as React from 'react';
import type { PanelProps } from '../interface';
export type ItemType = Omit<PanelProps, 'collapsible'> & {
    collapsible: {
        start?: boolean;
        end?: boolean;
    };
};
/**
 * Convert `children` into `items`.
 */
export default function useItems(children: React.ReactNode): ItemType[];
