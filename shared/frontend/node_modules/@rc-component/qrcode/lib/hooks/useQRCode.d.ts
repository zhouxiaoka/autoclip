import { QrCode } from '../libs/qrcodegen';
import type { ErrorCorrectionLevel, ImageSettings } from '../interface';
export declare function useQRCode({ value, level, minVersion, includeMargin, marginSize, imageSettings, size, }: {
    value: string;
    level: ErrorCorrectionLevel;
    minVersion: number;
    includeMargin: boolean;
    marginSize?: number;
    imageSettings?: ImageSettings;
    size: number;
}): {
    qrcode: QrCode;
    margin: number;
    cells: boolean[][];
    numCells: number;
    calculatedImageSettings: {
        x: number;
        y: number;
        h: number;
        w: number;
        excavation: import("../interface").Excavation;
        opacity: number;
        crossOrigin: import("../interface").CrossOrigin;
    };
};
