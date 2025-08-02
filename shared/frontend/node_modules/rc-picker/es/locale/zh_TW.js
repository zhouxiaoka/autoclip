import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'zh_TW',
  today: '今天',
  now: '此刻',
  backToToday: '返回今天',
  ok: '確定',
  timeSelect: '選擇時間',
  dateSelect: '選擇日期',
  weekSelect: '選擇周',
  clear: '清除',
  week: '週',
  month: '月',
  year: '年',
  previousMonth: '上個月 (翻頁上鍵)',
  nextMonth: '下個月 (翻頁下鍵)',
  monthSelect: '選擇月份',
  yearSelect: '選擇年份',
  decadeSelect: '選擇年代',
  yearFormat: 'YYYY年',
  dateFormat: 'YYYY年M月D日',
  dateTimeFormat: 'YYYY年M月D日 HH時mm分ss秒',
  previousYear: '上一年 (Control鍵加左方向鍵)',
  nextYear: '下一年 (Control鍵加右方向鍵)',
  previousDecade: '上一年代',
  nextDecade: '下一年代',
  previousCentury: '上一世紀',
  nextCentury: '下一世紀',
  cellDateFormat: 'D',
  monthBeforeYear: false
});
export default locale;