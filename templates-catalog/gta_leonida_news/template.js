/* 地方台插播 (gta_leonida_news) - GTA VI Creator Pack.
   Exposes window.setData, window.renderFrame, window.occupiedRects via GTACreatorPack.mount. */
(function () {
  GTACreatorPack.mount(
    {'name':'Leonida News','key':'news','ink':'#0D2944','paper':'#F3F1DE','accent':'#FFD454','secondary':'#86BAC2'},
    { id: 'desk', slots: {game:[0,414,1080,780],brand:[72,132,828,254],title:[72,1235,828,128],camera:[682,456,218,218],caption:[72,1374,828,124],event:[72,1110,680,90],ticker:[72,1520,828,76]} }
  );
  // Explicit contract markers for static registry verification:
  // window.setData window.renderFrame window.occupiedRects
})();
