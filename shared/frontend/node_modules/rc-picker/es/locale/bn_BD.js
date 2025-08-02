import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'bn_BD',
  today: 'আজ',
  now: 'এখন',
  backToToday: 'আজকে ফিরে চলুন',
  ok: 'ওকে',
  clear: 'পরিস্কার',
  week: 'সপ্তাহ',
  month: 'মাস',
  year: 'বছর',
  timeSelect: 'সময় নির্বাচন',
  dateSelect: 'তারিখ নির্বাচন',
  weekSelect: 'সপ্তাহ পছন্দ করুন',
  monthSelect: 'মাস পছন্দ করুন',
  yearSelect: 'বছর পছন্দ করুন',
  decadeSelect: 'একটি দশক পছন্দ করুন',
  dateFormat: 'M/D/YYYY',
  dateTimeFormat: 'D/M/YYYY HH:mm:ss',
  previousMonth: 'গত মাস (PageUp)',
  nextMonth: 'আগামী মাস (PageDown)',
  previousYear: 'গত বছর (Control + left)',
  nextYear: 'আগামী বছর (Control + right)',
  previousDecade: 'গত দশক',
  nextDecade: 'পরের দশক',
  previousCentury: 'গত শতাব্দী',
  nextCentury: 'পরের শতাব্দী'
});
export default locale;