import os
from osgeo import gdal
import numpy as np
from osgeo import gdal,osr
from osgeo_utils import gdal2tiles
#os.environ["PROJ_IGNORE_CELESTIAL_BODY"] = "YES"
def combine_mask(base_tif: str, mask_tif: str, output_tif: str):
    print("Combining base and mask...")
    base = gdal.Open(base_tif)
    mask = gdal.Open(mask_tif)
    base_band = base.GetRasterBand(1).ReadAsArray()
    mask_band = mask.GetRasterBand(1).ReadAsArray()   
    combined = np.where(mask_band > 0, base_band, 0)
    driver = gdal.GetDriverByName("GTiff")
    out = driver.Create(
        output_tif,
        base.RasterXSize,
        base.RasterYSize,
        1,
        gdal.GDT_Byte
    )
    srs=osr.SpatialReference()
    srs.ImportFromProj4("+proj=stere +lat_0=90 +lon_0=0 +a=1737400 +b=1737400 +units=m +no_defs")
    
    out.SetProjection(base.GetProjection())
    out.SetGeoTransform(base.GetGeoTransform())
    out.GetRasterBand(1).WriteArray(combined)
    out.GetRasterBand(1).SetNoDataValue(0)
    out.FlushCache()
    print(f" Combined image written to {output_tif}")
    out = None
    base = None
    mask = None

def generate_tiles(input_tif: str, output_dir: str, zoom="0-8", viewer="leaflet"):
    print(" Generating tiles...")
    os.environ["PROJ_IGNORE_CELESTIAL_BODY"]="YES"
    args=[
        "-z", zoom,
        "-r", "near",
        "--processes=8",
        input_tif,
        output_dir
    ]
    print(f" Tiles saved in {output_dir}")
    if viewer != "none":
        args.insert(0,f"--webviewer={viewer}")
        print(f" Open {os.path.join(output_dir, 'leaflet.html')} for preview.")
    gdal2tiles.main(args)
    if viewer !="none":
        html_file=os.path.join(output_dir,f"{viewer}.html")
        if(os.path.exists(html_file)):
           print(f"Open {html_file} for preview")
if __name__ == "__main__":
    path="../images/"
    base = "../images/WAC_ROI_NORTH_SUMMER_004P.PYR.TIF"
    mask = "../images/WAC_ROI_NORTH_SUMMER_004P.MASK.TIF"
    combined = "../out/WAC_ROI_NORTH_SUMMER_004P.COMBINED.TIF"
    output = "../out/moon_polar_tiles"
    pyr_file=[f for f in os.listdir(path) if f.endswith(".PYR.TIF")]
    mask_file=[f for f in os.listdir(path)if f.endswith(".MASK.tiff")]
    i=0
    for pyr,mask in zip(pyr_file,mask_file):
        i+=1
       
        combined="../out/"+pyr[:-8]+".COMBINED."+"tiff"
        output=f"../out/moon_polar_tiles{i}"
        pyr="../images/"+pyr
        mask="../images/"+mask
        combine_mask(pyr, mask, combined)
        print(combined)
        print(output)
        generate_tiles(combined, output, zoom="0-8")

