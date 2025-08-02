import React from 'react';
import type { PanelProps } from '../interface';
export declare function getPtg(str: string): number;
/**
 * Save the size state.
 * Align the size into flex percentage base.
 */
export default function useSizes(items: PanelProps[], containerSize?: number): readonly [(string | number | undefined)[], number[], number[], number[], number[], React.Dispatch<React.SetStateAction<(string | number | undefined)[]>>];
