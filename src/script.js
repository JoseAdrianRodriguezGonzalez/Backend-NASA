
const moonRadius = 1737400;

const moonEllipsoid = new Cesium.Ellipsoid(
    moonRadius, moonRadius, moonRadius
);

const viewer = new Cesium.Viewer('cesiumContainer', {
    sceneMode: Cesium.SceneMode.SCENE3D,
    globe: new Cesium.Globe(moonEllipsoid),
    baseLayerPicker: false,
    terrainProvider: new Cesium.EllipsoidTerrainProvider({ ellipsoid: moonEllipsoid })
});
const northPoleRect = [
  Cesium.Rectangle.fromDegrees(-180, 60, -90, 90), // Tile 1
  Cesium.Rectangle.fromDegrees(-90, 60, 0, 90),    // Tile 2
  Cesium.Rectangle.fromDegrees(0, 60, 90, 90),     // Tile 3
  Cesium.Rectangle.fromDegrees(90, 60, 180, 90),   // Tile 4
  Cesium.Rectangle.fromDegrees(-180, 30, -90, 60), // Tile 5
  Cesium.Rectangle.fromDegrees(-90, 30, 0, 60),    // Tile 6
  Cesium.Rectangle.fromDegrees(0, 30, 90, 60),     // Tile 7
  Cesium.Rectangle.fromDegrees(90, 30, 360, 60),   // Tile 8
];
const southPoleRectangles = [
    Cesium.Rectangle.fromDegrees(-45, -90, 45, -60), // Tile 9
    Cesium.Rectangle.fromDegrees(-90, -60, 0, -30),  // Tile 10
    Cesium.Rectangle.fromDegrees(0, -60, 90, -30),   // Tile 11
    Cesium.Rectangle.fromDegrees(90, -60, 180, -30), // Tile 12
    Cesium.Rectangle.fromDegrees(-45, -30, 45, 0)    // Tile 13
];
const equatorialRectangles = [];
for (let i = 0; i < 35; i++) {
    equatorialRectangles.push(Cesium.Rectangle.fromDegrees(
        -180 + i * (360 / 35), 0, 
        -180 + (i + 1) * (360 / 35), 30 // adjust latitude for equator
    ));
}
const allRectangles = [
  ...northPoleRect,        // Tile 0 (north)
  ...equatorialRectangles,        // Tiles 1-8 (mid-latitudes)
  ...southPoleRectangles         // Tile 9 (south)
];
for (let i = 0; i < allRectangles.length; i++) {
    const moonTiles = new Cesium.UrlTemplateImageryProvider({
        url: `http://127.0.0.1:8000/out1/moon_polar_tiles${i+1}/{z}/{x}/{y}.png`,
        tilingScheme: new Cesium.GeographicTilingScheme(),
        rectangle: allRectangles[i],
        maximumLevel: 8
    });
    moonTiles.tileDiscardPolicy = new Cesium.DiscardEmptyTileImagePolicy();
    viewer.imageryLayers.addImageryProvider(moonTiles);
}


// Fly camera to the Moon
viewer.camera.flyTo({
    destination: new Cesium.Cartesian3(0, 0, -moonRadius * 3),
    orientation: {
        direction: new Cesium.Cartesian3(0, 0, 1), // look at the Moon
        up: new Cesium.Cartesian3(0, 1, 0)
    }
});