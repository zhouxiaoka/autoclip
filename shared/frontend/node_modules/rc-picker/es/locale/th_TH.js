import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'th_TH',
  today: 'วันนี้',
  now: 'ตอนนี้',
  backToToday: 'กลับไปยังวันนี้',
  ok: 'ตกลง',
  clear: 'ลบล้าง',
  week: 'สัปดาห์',
  month: 'เดือน',
  year: 'ปี',
  timeSelect: 'เลือกเวลา',
  dateSelect: 'เลือกวัน',
  monthSelect: 'เลือกเดือน',
  yearSelect: 'เลือกปี',
  decadeSelect: 'เลือกทศวรรษ',
  dateFormat: 'D/M/YYYY',
  dateTimeFormat: 'D/M/YYYY HH:mm:ss',
  previousMonth: 'เดือนก่อนหน้า (PageUp)',
  nextMonth: 'เดือนถัดไป (PageDown)',
  previousYear: 'ปีก่อนหน้า (Control + left)',
  nextYear: 'ปีถัดไป (Control + right)',
  previousDecade: 'ทศวรรษก่อนหน้า',
  nextDecade: 'ทศวรรษถัดไป',
  previousCentury: 'ศตวรรษก่อนหน้า',
  nextCentury: 'ศตวรรษถัดไป'
});
export default locale;