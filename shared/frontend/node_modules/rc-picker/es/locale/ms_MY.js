import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'ms_MY',
  today: 'Hari ini',
  now: 'Sekarang',
  backToToday: 'Kembali ke hari ini',
  ok: 'OK',
  timeSelect: 'Pilih masa',
  dateSelect: 'Pilih tarikh',
  weekSelect: 'Pilih minggu',
  clear: 'Padam',
  week: 'Minggu',
  month: 'Bulan',
  year: 'Tahun',
  previousMonth: 'Bulan lepas',
  nextMonth: 'Bulan depan',
  monthSelect: 'Pilih bulan',
  yearSelect: 'Pilih tahun',
  decadeSelect: 'Pilih dekad',
  dateFormat: 'M/D/YYYY',
  dateTimeFormat: 'M/D/YYYY HH:mm:ss',
  previousYear: 'Tahun lepas (Ctrl+left)',
  nextYear: 'Tahun depan (Ctrl+right)',
  previousDecade: 'Dekad lepas',
  nextDecade: 'Dekad depan',
  previousCentury: 'Abad lepas',
  nextCentury: 'Abad depan',
  monthBeforeYear: false
});
export default locale;