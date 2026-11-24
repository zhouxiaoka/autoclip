/* 翻车回放 (gta_wasted) - GTA VI Creator Pack.
   Exposes window.setData, window.renderFrame, window.occupiedRects via GTACreatorPack.mount. */
(function () {
  GTACreatorPack.mount(
    {'name':'Wasted','key':'wasted','ink':'#171717','paper':'#F2EFE8','accent':'#FF5145','secondary':'#ADAAA3'},
    { id: 'split', slots: {game:[0,440,1080,735],brand:[72,132,828,88],title:[72,243,828,164],camera:[72,1234,286,312],caption:[388,1234,512,312],event:[72,977,828,170],ticker:[72,1552,828,44]} }
  );
  // Explicit contract markers for static registry verification:
  // window.setData window.renderFrame window.occupiedRects
})();
