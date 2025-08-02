import * as React from 'react';
import type { RenderFunc, SharedConfig } from '../interface';
export default function useChildren<T>(list: T[], startIndex: number, endIndex: number, scrollWidth: number, offsetX: number, setNodeRef: (item: T, element: HTMLElement) => void, renderFunc: RenderFunc<T>, { getKey }: SharedConfig<T>): React.JSX.Element[];
