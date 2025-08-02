"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _objectSpread2 = _interopRequireDefault(require("@babel/runtime/helpers/objectSpread2"));
var _common = require("./common");
var locale = (0, _objectSpread2.default)((0, _objectSpread2.default)({}, _common.commonLocale), {}, {
  locale: 'ja_JP',
  today: '今日',
  now: '現在時刻',
  backToToday: '今日に戻る',
  ok: '確定',
  timeSelect: '時間を選択',
  dateSelect: '日時を選択',
  weekSelect: '週を選択',
  clear: 'クリア',
  week: '週',
  month: '月',
  year: '年',
  previousMonth: '前月 (ページアップキー)',
  nextMonth: '翌月 (ページダウンキー)',
  monthSelect: '月を選択',
  yearSelect: '年を選択',
  decadeSelect: '年代を選択',
  yearFormat: 'YYYY年',
  dateFormat: 'YYYY年M月D日',
  dateTimeFormat: 'YYYY年M月D日 HH時mm分ss秒',
  previousYear: '前年 (Controlを押しながら左キー)',
  nextYear: '翌年 (Controlを押しながら右キー)',
  previousDecade: '前の年代',
  nextDecade: '次の年代',
  previousCentury: '前の世紀',
  nextCentury: '次の世紀',
  monthBeforeYear: false
});
var _default = exports.default = locale;