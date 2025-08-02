export declare class Mode {
    static readonly NUMERIC: Mode;
    static readonly ALPHANUMERIC: Mode;
    static readonly BYTE: Mode;
    static readonly KANJI: Mode;
    static readonly ECI: Mode;
    modeBits: number;
    private numBitsCharCount;
    private constructor();
    numCharCountBits(ver: number): number;
}
export declare class Ecc {
    static readonly LOW: Ecc;
    static readonly MEDIUM: Ecc;
    static readonly QUARTILE: Ecc;
    static readonly HIGH: Ecc;
    ordinal: number;
    formatBits: number;
    private constructor();
}
export declare class QrSegment {
    static makeBytes(data: Readonly<number[]>): QrSegment;
    static makeNumeric(digits: string): QrSegment;
    static makeAlphanumeric(text: string): QrSegment;
    static makeSegments(text: string): QrSegment[];
    static makeEci(assignVal: number): QrSegment;
    static isNumeric(text: string): boolean;
    static isAlphanumeric(text: string): boolean;
    mode: Mode;
    numChars: number;
    private bitData;
    constructor(mode: Mode, numChars: number, bitData: number[]);
    getData(): number[];
    static getTotalBits(segs: Readonly<QrSegment[]>, version: number): number;
    private static toUtf8ByteArray;
    private static readonly NUMERIC_REGEX;
    private static readonly ALPHANUMERIC_REGEX;
    private static readonly ALPHANUMERIC_CHARSET;
}
export declare class QrCode {
    static encodeText(text: string, ecl: Ecc): QrCode;
    static encodeBinary(data: Readonly<number[]>, ecl: Ecc): QrCode;
    static encodeSegments(segs: Readonly<QrSegment[]>, oriEcl: Ecc, minVersion?: number, maxVersion?: number, mask?: number, boostEcl?: boolean): QrCode;
    readonly size: number;
    readonly mask: number;
    private readonly modules;
    private readonly isFunction;
    version: number;
    errorCorrectionLevel: Ecc;
    constructor(version: number, errorCorrectionLevel: Ecc, dataCodewords: Readonly<number[]>, oriMsk: number);
    getModule(x: number, y: number): boolean;
    getModules(): boolean[][];
    private drawFunctionPatterns;
    private drawFormatBits;
    private drawVersion;
    private drawFinderPattern;
    private drawAlignmentPattern;
    private setFunctionModule;
    private addEccAndInterleave;
    private drawCodewords;
    private applyMask;
    private getPenaltyScore;
    private getAlignmentPatternPositions;
    private static getNumRawDataModules;
    private static getNumDataCodewords;
    private static reedSolomonComputeDivisor;
    private static reedSolomonComputeRemainder;
    private static reedSolomonMultiply;
    private finderPenaltyCountPatterns;
    private finderPenaltyTerminateAndCount;
    private finderPenaltyAddHistory;
    static readonly MIN_VERSION: number;
    static readonly MAX_VERSION: number;
    private static readonly PENALTY_N1;
    private static readonly PENALTY_N2;
    private static readonly PENALTY_N3;
    private static readonly PENALTY_N4;
    private static readonly ECC_CODEWORDS_PER_BLOCK;
    private static readonly NUM_ERROR_CORRECTION_BLOCKS;
}
