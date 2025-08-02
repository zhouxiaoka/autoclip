"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _ms_MY = _interopRequireDefault(require("rc-pagination/lib/locale/ms_MY"));
var _ms_MY2 = _interopRequireDefault(require("../calendar/locale/ms_MY"));
var _ms_MY3 = _interopRequireDefault(require("../date-picker/locale/ms_MY"));
var _ms_MY4 = _interopRequireDefault(require("../time-picker/locale/ms_MY"));
const typeTemplate = '${label} bukan ${type} jenis yang sah';
const localeValues = {
  locale: 'ms-my',
  Pagination: _ms_MY.default,
  DatePicker: _ms_MY3.default,
  TimePicker: _ms_MY4.default,
  Calendar: _ms_MY2.default,
  global: {
    placeholder: 'Sila pilih',
    close: 'Tutup'
  },
  Table: {
    filterTitle: 'Cari dengan tajuk',
    filterConfirm: 'OK',
    filterReset: 'Menetapkan semula',
    emptyText: 'Tiada data',
    selectAll: 'Pilih Semua',
    selectInvert: 'Terbalikkan',
    filterEmptyText: 'Tiada Saringan',
    filterCheckAll: 'Semak Semua',
    filterSearchPlaceholder: 'Cari',
    selectNone: 'Kosong Semua',
    selectionAll: 'Semua Data',
    sortTitle: 'Urutkan',
    expand: 'Buka',
    collapse: 'Tutup',
    triggerDesc: 'Turun',
    triggerAsc: 'Naik',
    cancelSort: 'Batal Urut'
  },
  Modal: {
    okText: 'OK',
    cancelText: 'Batal',
    justOkText: 'OK'
  },
  Tour: {
    Next: 'Seterusnya',
    Previous: 'Sebelumnya',
    Finish: 'Tamat'
  },
  Popconfirm: {
    okText: 'OK',
    cancelText: 'Batal'
  },
  Transfer: {
    titles: ['', ''],
    notFoundContent: 'Tidak dijumpai',
    searchPlaceholder: 'Carian di sini',
    itemUnit: 'item',
    itemsUnit: 'item',
    remove: 'Buang',
    selectCurrent: 'Pilih Halaman Ini',
    removeCurrent: 'Buang Dari Halaman Ini',
    selectAll: 'Pilih Semua',
    removeAll: 'Buang Semua',
    selectInvert: 'Balik Pilihan'
  },
  Upload: {
    uploading: 'Sedang memuat naik...',
    removeFile: 'Buang fail',
    uploadError: 'Masalah muat naik',
    previewFile: 'Tengok fail',
    downloadFile: 'Muat turun fail'
  },
  Empty: {
    description: 'Tiada data'
  },
  Icon: {
    icon: 'ikon'
  },
  Text: {
    edit: 'Sunting',
    copy: 'Salin',
    copied: 'Berjaya menyalin',
    expand: 'Kembang'
  },
  Form: {
    optional: '(Opsional)',
    defaultValidateMessages: {
      default: 'Ralat pengesahan untuk ${label}',
      required: 'Isi ${label}',
      enum: '${label} mesti salah satu dari [${enum}]',
      whitespace: '${label} tidak boleh kosong',
      date: {
        format: 'Format tarikh ${label} salah',
        parse: '${label} tidak boleh jadi tarikh',
        invalid: '${label} adalah tarikh tidak sah'
      },
      types: {
        string: typeTemplate,
        method: typeTemplate,
        array: typeTemplate,
        object: typeTemplate,
        number: typeTemplate,
        date: typeTemplate,
        boolean: typeTemplate,
        integer: typeTemplate,
        float: typeTemplate,
        regexp: typeTemplate,
        email: typeTemplate,
        url: typeTemplate,
        hex: typeTemplate
      },
      string: {
        len: '${label} mesti ${len} aksara',
        min: 'Min ${min} aksara',
        max: 'Max ${max} aksara',
        range: '${label} antara ${min}-${max} aksara'
      },
      number: {
        len: '${label} sama dengan ${len}',
        min: 'Min ${min}',
        max: 'Max ${max}',
        range: '${label} antara ${min}-${max}'
      },
      array: {
        len: '${len} ${label}',
        min: 'Min ${min} ${label}',
        max: 'Max ${max} ${label}',
        range: '${label} antara ${min}-${max}'
      },
      pattern: {
        mismatch: '${label} tidak sesuai ${pattern}'
      }
    }
  },
  Image: {
    preview: 'Pratonton'
  },
  QRCode: {
    expired: 'Kod QR luput',
    refresh: 'Segar Semula'
  },
  ColorPicker: {
    presetEmpty: 'Tiada',
    transparent: 'Tidak tembus cahaya',
    singleColor: 'Warna tunggal',
    gradientColor: 'Warna gradien'
  }
};
var _default = exports.default = localeValues;