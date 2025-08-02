import type { CrossOrigin, ERROR_LEVEL_MAPPED_TYPE, ErrorCorrectionLevel, Excavation, ImageSettings, Modules } from './interface';
export declare const ERROR_LEVEL_MAP: ERROR_LEVEL_MAPPED_TYPE;
export declare const DEFAULT_SIZE = 128;
export declare const DEFAULT_LEVEL: ErrorCorrectionLevel;
export declare const DEFAULT_BACKGROUND_COLOR = "#FFFFFF";
export declare const DEFAULT_FRONT_COLOR = "#000000";
export declare const DEFAULT_NEED_MARGIN = false;
export declare const DEFAULT_MINVERSION = 1;
export declare const SPEC_MARGIN_SIZE = 4;
export declare const DEFAULT_MARGIN_SIZE = 0;
export declare const DEFAULT_IMG_SCALE = 0.1;
/**
 * Generate a path string from modules
 * @param modules
 * @param margin
 * @returns
 */
export declare function generatePath(modules: Modules, margin?: number): string;
/**
 * Excavate modules
 * @param modules
 * @param excavation
 * @returns
 */
export declare function excavateModules(modules: Modules, excavation: Excavation): Modules;
/**
 * Get image settings
 * @param cells The modules of the QR code
 * @param size The size of the QR code
 * @param margin
 * @param imageSettings
 * @returns
 */
export declare function getImageSettings(cells: Modules, size: number, margin: number, imageSettings?: ImageSettings): null | {
    x: number;
    y: number;
    h: number;
    w: number;
    excavation: Excavation | null;
    opacity: number;
    crossOrigin: CrossOrigin;
};
/**
 * Get margin size
 * @param needMargin Whether need margin
 * @param marginSize Custom margin size
 * @returns
 */
export declare function getMarginSize(needMargin: boolean, marginSize?: number): number;
/**
 * Check if Path2D is supported
 */
export declare const isSupportPath2d: boolean;
