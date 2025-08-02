import CalendarLocale from "rc-picker/es/locale/id_ID";
import TimePickerLocale from '../../time-picker/locale/id_ID';
// Merge into a locale object
const locale = {
  lang: Object.assign({
    placeholder: 'Pilih tanggal',
    yearPlaceholder: 'Pilih tahun',
    quarterPlaceholder: 'Pilih kuartal',
    monthPlaceholder: 'Pilih bulan',
    weekPlaceholder: 'Pilih minggu',
    rangePlaceholder: ['Tanggal awal', 'Tanggal akhir'],
    rangeYearPlaceholder: ['Tahun awal', 'Tahun akhir'],
    rangeQuarterPlaceholder: ['Kuartal awal', 'Kuartal akhir'],
    rangeMonthPlaceholder: ['Bulan awal', 'Bulan akhir'],
    rangeWeekPlaceholder: ['Minggu awal', 'Minggu akhir']
  }, CalendarLocale),
  timePickerLocale: Object.assign({}, TimePickerLocale)
};
// All settings at:
// https://github.com/ant-design/ant-design/blob/master/components/date-picker/locale/example.json
export default locale;