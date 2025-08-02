import type { CSSProperties } from 'react';
import type { Ecc, QrCode } from './libs/qrcodegen';
export type Modules = ReturnType<QrCode['getModules']>;
export type Excavation = {
    x: number;
    y: number;
    w: number;
    h: number;
};
export type ErrorCorrectionLevel = 'L' | 'M' | 'Q' | 'H';
export type CrossOrigin = 'anonymous' | 'use-credentials' | '' | undefined;
export type ERROR_LEVEL_MAPPED_TYPE = {
    [index in ErrorCorrectionLevel]: Ecc;
};
export type ImageSettings = {
    src: string;
    height: number;
    width: number;
    excavate: boolean;
    x?: number;
    y?: number;
    opacity?: number;
    crossOrigin?: CrossOrigin;
};
export type QRProps = {
    value: string;
    size?: number;
    level?: ErrorCorrectionLevel;
    bgColor?: string;
    fgColor?: string;
    style?: CSSProperties;
    includeMargin?: boolean;
    marginSize?: number;
    imageSettings?: ImageSettings;
    title?: string;
    minVersion?: number;
};
export type QRPropsCanvas = QRProps & React.CanvasHTMLAttributes<HTMLCanvasElement>;
export type QRPropsSVG = QRProps & React.SVGAttributes<SVGSVGElement>;
