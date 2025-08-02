import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'tr_TR',
  today: 'Bugün',
  now: 'Şimdi',
  backToToday: 'Bugüne Geri Dön',
  ok: 'Tamam',
  clear: 'Temizle',
  week: 'Hafta',
  month: 'Ay',
  year: 'Yıl',
  timeSelect: 'Zaman Seç',
  dateSelect: 'Tarih Seç',
  monthSelect: 'Ay Seç',
  yearSelect: 'Yıl Seç',
  decadeSelect: 'On Yıl Seç',
  dateFormat: 'DD/MM/YYYY',
  dateTimeFormat: 'DD/MM/YYYY HH:mm:ss',
  previousMonth: 'Önceki Ay (PageUp)',
  nextMonth: 'Sonraki Ay (PageDown)',
  previousYear: 'Önceki Yıl (Control + Sol)',
  nextYear: 'Sonraki Yıl (Control + Sağ)',
  previousDecade: 'Önceki On Yıl',
  nextDecade: 'Sonraki On Yıl',
  previousCentury: 'Önceki Yüzyıl',
  nextCentury: 'Sonraki Yüzyıl',
  shortWeekDays: ['Paz', 'Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt'],
  shortMonths: ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara']
});
export default locale;