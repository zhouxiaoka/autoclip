import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { commonLocale } from "./common";
var locale = _objectSpread(_objectSpread({}, commonLocale), {}, {
  locale: 'id_ID',
  today: 'Hari ini',
  now: 'Sekarang',
  backToToday: 'Kembali ke hari ini',
  ok: 'Baik',
  clear: 'Bersih',
  week: 'Minggu',
  month: 'Bulan',
  year: 'Tahun',
  timeSelect: 'pilih waktu',
  dateSelect: 'pilih tanggal',
  weekSelect: 'Pilih satu minggu',
  monthSelect: 'Pilih satu bulan',
  yearSelect: 'Pilih satu tahun',
  decadeSelect: 'Pilih satu dekade',
  dateFormat: 'D/M/YYYY',
  dateTimeFormat: 'D/M/YYYY HH:mm:ss',
  previousMonth: 'Bulan sebelumnya (PageUp)',
  nextMonth: 'Bulan selanjutnya (PageDown)',
  previousYear: 'Tahun lalu (Control + kiri)',
  nextYear: 'Tahun selanjutnya (Kontrol + kanan)',
  previousDecade: 'Dekade terakhir',
  nextDecade: 'Dekade berikutnya',
  previousCentury: 'Abad terakhir',
  nextCentury: 'Abad berikutnya'
});
export default locale;