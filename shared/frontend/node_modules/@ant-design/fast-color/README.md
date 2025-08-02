# @ant-design/fast-color

Fast Color Class

[![NPM version][npm-image]][npm-url]
[![npm download][download-image]][download-url]
[![build status][github-actions-image]][github-actions-url]
[![Test coverage][codecov-image]][codecov-url]
[![bundle size][bundlephobia-image]][bundlephobia-url]
[![dumi][dumi-image]][dumi-url]

[npm-image]: http://img.shields.io/npm/v/@ant-design/fast-color.svg?style=flat-square
[npm-url]: http://npmjs.org/package/@ant-design/fast-color
[github-actions-image]: https://github.com/ant-design/fast-color/workflows/CI/badge.svg
[github-actions-url]: https://github.com/ant-design/fast-color/actions
[codecov-image]: https://img.shields.io/codecov/c/github/ant-design/fast-color/master.svg?style=flat-square
[codecov-url]: https://codecov.io/gh/ant-design/fast-color/branch/master
[david-url]: https://david-dm.org/ant-design/fast-color
[david-image]: https://david-dm.org/ant-design/fast-color/status.svg?style=flat-square
[david-dev-url]: https://david-dm.org/ant-design/fast-color?type=dev
[david-dev-image]: https://david-dm.org/ant-design/fast-color/dev-status.svg?style=flat-square
[download-image]: https://img.shields.io/npm/dm/@ant-design/fast-color.svg?style=flat-square
[download-url]: https://npmjs.org/package/@ant-design/fast-color
[bundlephobia-url]: https://bundlephobia.com/result?p=@ant-design/fast-color
[bundlephobia-image]: https://badgen.net/bundlephobia/minzip/@ant-design/fast-color
[dumi-image]: https://img.shields.io/badge/docs%20by-dumi-blue?style=flat-square
[dumi-url]: https://github.com/umijs/dumi

## Install

[![@ant-design/fast-color](https://nodei.co/npm/@ant-design/fast-color.png)](https://npmjs.org/package/@ant-design/fast-color)

## Usage

```js
import { FastColor } from '@ant-design/fast-color';

// input
new FastColor('#666'); // short hex
new FastColor('#66ccff'); // hex
new FastColor('#66ccffaa'); // hex with alpha
new FastColor('rgba(102, 204, 255, .5)'); // old css rgb syntax
new FastColor('rgb(102 204 255 / .5)'); // new css rgb syntax
new FastColor('hsl(270, 60, 40, .5)'); // old css hsl syntax, with or without unit
new FastColor('hsl(270deg 60% 40% / 50%)'); // new css hsl syntax, with or without unit
new FastColor({ r: 102, g: 204, b: 255, a: 0.5 }); // rgb object
new FastColor({ h: 270, s: 0.6, l: 0.4, a: 0.5 }); // hsl object
new FastColor({ h: 270, s: 0.6, v: 0.4, a: 0.5 }); // hsv object

// clone
const color = new FastColor('#66ccff');
const color2 = new FastColor(color); // clone via constructor
const color3 = color2.clone(); // call clone method

// output
color.toHexString(); // #66ccff
color.toRgb(); // Object { r: 102, g: 204, b: 255, a: 1 }
color.toRgbString(); // rgb(102,204,255)
color.toHsl(); // Object { h: 200, s: 0.6, l: 0.7, a: 1 }
color.toHslString(); // hsl(200,60%,70%)
color.toHsv(); // Object { h: 200, s: 0.6, v: 1, a: 1 }
```

## Compatibility

| [<img src="https://raw.githubusercontent.com/alrra/browser-logos/master/src/edge/edge_48x48.png" alt="IE / Edge" width="24px" height="24px" />](http://godban.github.io/browsers-support-badges/)<br>IE / Edge | [<img src="https://raw.githubusercontent.com/alrra/browser-logos/master/src/firefox/firefox_48x48.png" alt="Firefox" width="24px" height="24px" />](http://godban.github.io/browsers-support-badges/)<br>Firefox | [<img src="https://raw.githubusercontent.com/alrra/browser-logos/master/src/chrome/chrome_48x48.png" alt="Chrome" width="24px" height="24px" />](http://godban.github.io/browsers-support-badges/)<br>Chrome | [<img src="https://raw.githubusercontent.com/alrra/browser-logos/master/src/safari/safari_48x48.png" alt="Safari" width="24px" height="24px" />](http://godban.github.io/browsers-support-badges/)<br>Safari | [<img src="https://raw.githubusercontent.com/alrra/browser-logos/master/src/electron/electron_48x48.png" alt="Electron" width="24px" height="24px" />](http://godban.github.io/browsers-support-badges/)<br>Electron |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| IE11, Edge                                                                                                                                                                                                     | last 2 versions                                                                                                                                                                                                  | last 2 versions                                                                                                                                                                                              | last 2 versions                                                                                                                                                                                              | last 2 versions                                                                                                                                                                                                      |

## API

TODO

## License

@ant-design/fast-color is released under the MIT license.
