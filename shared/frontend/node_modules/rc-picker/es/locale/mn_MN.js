import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'mn_MN',
  today: 'Өнөөдөр',
  now: 'Одоо',
  backToToday: 'Өнөөдөрлүү буцах',
  ok: 'OK',
  clear: 'Цэвэрлэх',
  week: 'Долоо хоног',
  month: 'Сар',
  year: 'Жил',
  timeSelect: 'Цаг сонгох',
  dateSelect: 'Огноо сонгох',
  weekSelect: '7 хоног сонгох',
  monthSelect: 'Сар сонгох',
  yearSelect: 'Жил сонгох',
  decadeSelect: 'Арван сонгох',
  dateFormat: 'YYYY/MM/DD',
  dayFormat: 'DD',
  dateTimeFormat: 'YYYY/MM/DD HH:mm:ss',
  previousMonth: 'Өмнөх сар (PageUp)',
  nextMonth: 'Дараа сар (PageDown)',
  previousYear: 'Өмнөх жил (Control + left)',
  nextYear: 'Дараа жил (Control + right)',
  previousDecade: 'Өмнөх арван',
  nextDecade: 'Дараа арван',
  previousCentury: 'Өмнөх зуун',
  nextCentury: 'Дараа зуун'
});
export default locale;