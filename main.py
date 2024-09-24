import sys
import os
import io
import re
import win32file
import win32con
import pywintypes
import piexif
import pyexiv2
import whatimage
import pillow_heif
import exifread
from datetime import datetime,timedelta
from pathlib import Path
from PIL import Image
from PIL.ExifTags import TAGS
from pymediainfo import MediaInfo

# pip3 install pywin32
# pip install Pillow
# pip install piexif
# pip install pyexiv2
# pip install pymediainfo
# pip install pillow_heif
# pip install whatimage
# pip install exifread


# 注册 HEIC 文件打开器,让Pillow 库就能够识别和打开 HEIC 格式的文件
pillow_heif.register_heif_opener()
# type: 0为图片,1为视频
def get_exif_data(path, type = 0):
    try:
        if type:
            # 解析视频文件
            media_info = MediaInfo.parse(path)
            # 遍历所有轨道，寻找视频轨道的拍摄日期
            for track in media_info.tracks:
                if track.track_type in ['General', 'Video']:
                    # 尝试获取编码日期，这可能与拍摄日期相关
                    encoded_date = getattr(track, 'encoded_date', None)
                    if not encoded_date:
                        encoded_date = getattr(track, 'tagged_date', None)
                    if encoded_date:
                        print(f"视频文件 {path} 读取到的拍摄日期为: {encoded_date}")
                        return datetime.strptime(encoded_date, '%Y-%m-%d %H:%M:%S UTC')
                    else:
                        print(f"视频文件 {path}拍摄日期未找到。")
                        # 从创建时间和修改时间中查找最早的时间
                        return find_last_time(track)
                    break
        else:
            with open(path, 'rb') as f:
                file_data = f.read()
                # 判断照片格式
                fmt = whatimage.identify_image(file_data)
                if fmt in ['heic']:
                    DateTimeOriginal = read_heic_exif(path)
                elif fmt in ['tiff']:
                    DateTimeOriginal = read_tiff_exif(path)
                else:
                    DateTimeOriginal = read_image_exif(path)
                if DateTimeOriginal:
                    return datetime.strptime(DateTimeOriginal, '%Y:%m:%d %H:%M:%S')
                else:
                    return datetime.now()
    except Exception as e:
        print(f"Error: {e}")
        return None

def find_last_time(track):
    creation_date = getattr(track, 'file_creation_date', None)
    modification_date = getattr(track, 'file_last_modification_date', None)
    if creation_date:
        creation_date = datetime.strptime(creation_date, '%Y-%m-%d %H:%M:%S.%f UTC')
    if modification_date:
        modification_date = datetime.strptime(modification_date, '%Y-%m-%d %H:%M:%S.%f UTC')

    if creation_date.year > modification_date.year:
        return modification_date

    return creation_date

def read_heic_exif(heic_path):
    # 打开 HEIC 文件
    image = Image.open(heic_path)
    exif_data = image.info["exif"]
    if exif_data:
        fstream = io.BytesIO(exif_data[6:])
        exifdata = exifread.process_file(fstream,details=False)
        imageDateTime = str(exifdata.get("Image DateTime"))
        return imageDateTime
    else:
        return "No EXIF data found."

def read_image_exif(image_path):
    try:
        image = Image.open(image_path)
        exif_data = {
                    # 对于 image._getexif() 返回的字典中的每个键值对，如果键在 TAGS 字典中，并且对应的标签名是 'DateTimeOriginal'，则将这个键值对添加到新字典中。最终，这个新字典将只包含原始拍摄日期时间的键值对。
                    TAGS[key]: value
                    for key, value in image._getexif().items()
                    if key in TAGS and TAGS[key] == 'DateTimeOriginal'
                }
        return exif_data.get('DateTimeOriginal', None)
    except Exception as e:
        print(f"Error: {e}")
        return None

# DNG格式照片
def read_tiff_exif(image_path):
    image = Image.open(image_path)
    # TAGS：用于映射图像文件的0th IFD（Image File Directory）中的EXIF标签。
    exif_data = {
                TAGS[key]: value
                for key, value in image.tag.items()
                if key in TAGS and TAGS[key] == 'DateTime'
            }
    return exif_data.get('DateTime', 'No拍摄日期信息')[0]

def set_exif_data(image_path, new_time):
    try:
        # 读取图片的EXIF数据
        exif_dict = piexif.load(image_path)
        # EXIF数据中拍摄时间的标签是0x9003 (DateTimeOriginal)
        # 将datetime对象格式化为EXIF所需的字符串格式
        formatted_time = new_time.strftime('%Y:%m:%d %H:%M:%S')

        # 修改EXIF数据中的拍摄时间
        if "Exif" in exif_dict:
            exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = formatted_time
        else:
            # 如果没有Exif信息，则创建一个新的Exif信息
            exif_dict["Exif"] = {}
            exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = formatted_time

        # 将修改后的EXIF数据写回到图片中
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, image_path)
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        files = [file for file in path.rglob("*.*")]
        for file in files:
            image_path = file._raw_paths[0]
            file_suffix = file.suffix.upper()
            if file_suffix in ['.JPG', '.PNG', '.DNG', '.HEIC']:
                time_obj = get_exif_data(image_path)
            elif file_suffix in ['.MP4', '.MOV']:
                time_obj = get_exif_data(image_path, 1)
            if time_obj:
                # ios目录格式，获取目录标识的时间
                parent_name = file.parent.name
                if re.match(r'^\d{6}\_\_$', parent_name):
                    parent_year = int(parent_name[:4])
                    parent_month = int(parent_name[4:6])
                    # 当拍摄时间大于所在目录时，为照片的数据在移动过程中错误，修改年份和月份
                    if time_obj.year > parent_year:
                        time_obj = datetime(parent_year, parent_month, time_obj.day, time_obj.hour, time_obj.minute, time_obj.second)
                        set_exif_data(image_path, time_obj)
                formatted_time = time_obj.strftime('%Y_%m_%d_%H_%M_%S')
                image_parent_path = file.parent._raw_paths[0]
                new_path = f"{image_parent_path}\\{formatted_time}_{file.name}"
                # 照片不为年_月_日_时_分_才更名
                if re.match(r'^\d{4}\_(\d{2}_){5}', file.name):
                    new_path = image_path
                else:
                    os.rename(image_path, f"{image_parent_path}\\{formatted_time}_{file.name}")
                # 将time_obj对象转换为时间戳
                timestamp = time_obj.timestamp()
                # 将datetime对象转换为pywintypes.Time对象
                file_time = pywintypes.Time(timestamp)
                # 获取文件的句柄
                handle = win32file.CreateFile(
                    new_path,
                    win32file.GENERIC_WRITE,
                    0,
                    None,
                    win32con.OPEN_EXISTING,
                    0,
                    None
                )
                # 设置文件的创建日期
                win32file.SetFileTime(handle, file_time, file_time, file_time)
            else:
                print(f"{image_path}无拍摄日期")
