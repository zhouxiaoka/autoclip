/* 罪城落日 (gta_vice_sunset) - GTA VI Creator Pack.
   Exposes window.setData, window.renderFrame, window.occupiedRects via GTACreatorPack.mount. */
(function () {
  GTACreatorPack.mount(
    {'name':'Vice City Sunset','key':'sunset','ink':'#26162F','paper':'#FFF1D4','accent':'#FF978E','secondary':'#FFD38E'},
    { id: 'coast', slots: {game:[0,0,1080,1500],brand:[72,132,828,280],title:[72,1200,828,130],camera:[72,1354,215,215],caption:[318,1354,582,215],event:[72,1080,710,98],ticker:[72,1572,828,24]} }
  );
  // Explicit contract markers for static registry verification:
  // window.setData window.renderFrame window.occupiedRects
})();
