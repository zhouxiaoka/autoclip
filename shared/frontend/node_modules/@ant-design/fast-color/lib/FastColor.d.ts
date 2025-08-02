import type { ColorInput, HSL, HSV, RGB } from './types';
export declare class FastColor {
    /**
     * All FastColor objects are valid. So isValid is always true. This property is kept to be compatible with TinyColor.
     */
    isValid: boolean;
    /**
     * Red, R in RGB
     */
    r: number;
    /**
     * Green, G in RGB
     */
    g: number;
    /**
     * Blue, B in RGB
     */
    b: number;
    /**
     * Alpha/Opacity, A in RGBA/HSLA
     */
    a: number;
    private _h?;
    private _s?;
    private _l?;
    private _v?;
    private _max?;
    private _min?;
    private _brightness?;
    constructor(input: ColorInput);
    setR(value: number): this;
    setG(value: number): this;
    setB(value: number): this;
    setA(value: number): this;
    setHue(value: number): this;
    /**
     * Returns the perceived luminance of a color, from 0-1.
     * @see http://www.w3.org/TR/2008/REC-WCAG20-20081211/#relativeluminancedef
     */
    getLuminance(): number;
    getHue(): number;
    getSaturation(): number;
    getLightness(): number;
    getValue(): number;
    /**
     * Returns the perceived brightness of the color, from 0-255.
     * Note: this is not the b of HSB
     * @see http://www.w3.org/TR/AERT#color-contrast
     */
    getBrightness(): number;
    darken(amount?: number): this;
    lighten(amount?: number): this;
    /**
     * Mix the current color a given amount with another color, from 0 to 100.
     * 0 means no mixing (return current color).
     */
    mix(input: ColorInput, amount?: number): this;
    /**
     * Mix the color with pure white, from 0 to 100.
     * Providing 0 will do nothing, providing 100 will always return white.
     */
    tint(amount?: number): this;
    /**
     * Mix the color with pure black, from 0 to 100.
     * Providing 0 will do nothing, providing 100 will always return black.
     */
    shade(amount?: number): this;
    onBackground(background: ColorInput): this;
    isDark(): boolean;
    isLight(): boolean;
    equals(other: FastColor): boolean;
    clone(): this;
    toHexString(): string;
    /** CSS support color pattern */
    toHsl(): HSL;
    /** CSS support color pattern */
    toHslString(): string;
    /** Same as toHsb */
    toHsv(): HSV;
    toRgb(): RGB;
    toRgbString(): string;
    toString(): string;
    /** Return a new FastColor object with one channel changed */
    private _sc;
    private _c;
    private getMax;
    private getMin;
    private fromHexString;
    private fromHsl;
    private fromHsv;
    private fromHsvString;
    private fromHslString;
    private fromRgbString;
}
