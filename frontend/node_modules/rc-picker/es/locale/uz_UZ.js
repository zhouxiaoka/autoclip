import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'uz_UZ',
  today: 'Bugun',
  now: 'Hozir',
  backToToday: 'Bugunga qaytish',
  ok: 'OK',
  clear: 'Toza',
  week: 'Xafta',
  month: 'Oy',
  year: 'Yil',
  timeSelect: 'vaqtni tanlang',
  dateSelect: 'sanani tanlang',
  weekSelect: 'Haftani tanlang',
  monthSelect: 'Oyni tanlang',
  yearSelect: 'Yilni tanlang',
  decadeSelect: "O'n yilni tanlang",
  dateFormat: 'M/D/YYYY',
  dateTimeFormat: 'M/D/YYYY HH:mm:ss',
  previousMonth: 'Oldingi oy (PageUp)',
  nextMonth: 'Keyingi oy (PageDown)',
  previousYear: "O'tgan yili (Control + left)",
  nextYear: 'Keyingi yil (Control + right)',
  previousDecade: "Oxirgi o'n yil",
  nextDecade: "Keyingi o'n yil",
  previousCentury: "O'tgan asr",
  nextCentury: 'Keyingi asr'
});
export default locale;