import type React from 'react';
declare class CacheMap {
    maps: Record<string, number>;
    id: number;
    diffRecords: Map<React.Key, number>;
    constructor();
    set(key: React.Key, value: number): void;
    get(key: React.Key): number;
    /**
     * CacheMap will record the key changed.
     * To help to know what's update in the next render.
     */
    resetRecord(): void;
    getRecord(): Map<React.Key, number>;
}
export default CacheMap;
