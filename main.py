import sys
import os
import io
import re
import win32file
import win32con
import pywintypes
import piexif
import whatimage
import pillow_heif
import exifread
import shutil
import pytz
from datetime import datetime,timedelta
from pathlib import Path
from PIL import Image as PIL_Image
from PIL.ExifTags import TAGS
from pymediainfo import MediaInfo
from pyexiv2 import Image

# pip3 install pywin32
# pip install Pillow
# pip install piexif
# pip install pyexiv2
# pip install pymediainfo
# pip install pillow_heif
# pip install whatimage
# pip install exifread
# pip install pytz


# 实况照片字典
HEIC_DICT = {}
# 缺失exif数据的图片
EXIF_EMPTY = []

# 注册 HEIC 文件打开器,让Pillow 库就能够识别和打开 HEIC 格式的文件
pillow_heif.register_heif_opener()

# type: 0为图片,1为视频
def get_exif_data(path, type = 0):
    global HEIC_DICT
    try:
        if type:
            # 解析视频文件
            media_info = MediaInfo.parse(path)
            file_name = Path(path).stem
            if file_name in HEIC_DICT:
                return HEIC_DICT[file_name]['date']
            # 遍历所有轨道，寻找视频轨道的拍摄日期
            for track in media_info.tracks:
                if track.track_type in ['General', 'Video']:
                    # 尝试获取编码日期，这可能与拍摄日期相关
                    encoded_date = getattr(track, 'comapplequicktimecreationdate', None)
                    if encoded_date:
                        print(f"视频文件 {path} 读取到的拍摄日期为: {encoded_date}")
                        # 解析ISO格式的日期时间字符串
                        return datetime.fromisoformat(encoded_date)
                    if not encoded_date:
                        encoded_date = getattr(track, 'encoded_date', None)
                    if not encoded_date:
                        encoded_date = getattr(track, 'tagged_date', None)
                    if encoded_date:
                        print(f"视频文件 {path} 读取到的拍摄日期为: {encoded_date}")
                        # 设置UTC时区
                        utc_tz = pytz.timezone('UTC')
                        utc_time = datetime.strptime(encoded_date, '%Y-%m-%d %H:%M:%S UTC')
                        # 将解析的时间与UTC时区关联
                        utc_time = utc_tz.localize(utc_time)
                        # 设置北京时间时区
                        beijing_tz = pytz.timezone('Asia/Shanghai')
                        # 将UTC时间转换为北京时间
                        return utc_time.astimezone(beijing_tz)
                    else:
                        print(f"视频文件 {path}拍摄日期未找到，将按照创建日期和修改日期中最早的时间作为拍摄日期。")
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
                    # 存入heic
                    file_name = Path(path).stem
                    HEIC_DICT[file_name] = {
                        'date': datetime.strptime(DateTimeOriginal, '%Y:%m:%d %H:%M:%S')
                    }
                elif fmt in ['tiff']:
                    DateTimeOriginal = read_tiff_exif(path)
                elif fmt in ['png']:
                    DateTimeOriginal = read_png_exif(path)
                else:
                    DateTimeOriginal = read_image_exif(path)
                if DateTimeOriginal:
                    return datetime.strptime(DateTimeOriginal, '%Y:%m:%d %H:%M:%S')
                else:
                    return find_last_time_file(path)
    except Exception as e:
        print(f"Error: {e}")
        return None

# 查找视频最早时间
def find_last_time(track):
    creation_date = getattr(track, 'file_creation_date', None)
    modification_date = getattr(track, 'file_last_modification_date', None)
    if creation_date:
        creation_date = datetime.strptime(creation_date, '%Y-%m-%d %H:%M:%S.%f UTC')
    if modification_date:
        modification_date = datetime.strptime(modification_date, '%Y-%m-%d %H:%M:%S.%f UTC')
    if creation_date > modification_date:
        return modification_date
    return creation_date

# 查找文件最早时间
def find_last_time_file(file_path):
    try:
        # 获取文件状态信息
        file_stat = os.stat(file_path)
        # 获取文件的最后修改时间
        mod_time = datetime.fromtimestamp(file_stat.st_mtime)
        # 在Windows上，可以尝试获取文件的创建时间
        if os.name == 'nt':
            creation_time = datetime.fromtimestamp(file_stat.st_ctime)
        else:
            # 在Unix-like系统上，st_ctime通常表示状态更改时间
            creation_time = "Creation time is not available on this platform"
        if mod_time > creation_time:
            return creation_time
        return mod_time
    except Exception as e:
        print(f"Error: {e}")
        return None

# 读取heic照片信息
def read_heic_exif(heic_path):
    # 打开 HEIC 文件
    image = PIL_Image.open(heic_path)
    exif_data = image.info["exif"]
    if exif_data:
        fstream = io.BytesIO(exif_data[6:])
        exifdata = exifread.process_file(fstream, details=False)
        imageDateTime = str(exifdata.get("Image DateTime"))
        return imageDateTime
    else:
        print(f"{heic_path} No EXIF data found.")
        return None

# 读取png图片信息
def read_png_exif(heic_path):
    try:
        img = Image(image_path)
        load_exif = img.read_exif()
        if load_exif:
            return load_exif['Exif.Photo.DateTimeOriginal']
        return None
    except Exception as e:
        print(f"Warning: {image_path}未获取到时间相关数据")
        return None

# 读取普通照片信息
def read_image_exif(image_path):
    try:
        image = PIL_Image.open(image_path)
        exif_data = {
                    # 对于 image._getexif() 返回的字典中的每个键值对，如果键在 TAGS 字典中，并且对应的标签名是 'DateTimeOriginal'，则将这个键值对添加到新字典中。最终，这个新字典将只包含原始拍摄日期时间的键值对。
                    TAGS[key]: value
                    for key, value in image._getexif().items()
                    if key in TAGS and TAGS[key] == 'DateTimeOriginal'
                }
        return exif_data.get('DateTimeOriginal', None)
    except Exception as e:
        global EXIF_EMPTY
        print(f"Warning: {image_path}未获取到exif数据")
        EXIF_EMPTY.append(image_path)
        return None

# DNG格式照片
def read_tiff_exif(image_path):
    image = PIL_Image.open(image_path)
    # TAGS：用于映射图像文件的0th IFD（Image File Directory）中的EXIF标签。
    exif_data = {
                TAGS[key]: value
                for key, value in image.tag.items()
                if key in TAGS and TAGS[key] == 'DateTime'
            }
    return exif_data.get('DateTime', 'No拍摄日期信息')[0]

# 修改照片exif
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

# 修改图片XML
def set_XML_data(image_path, new_time):
    try:
        img = Image(image_path)
        formatted_time = new_time.strftime('%Y:%m:%d %H:%M:%S')
        # 用字典记录目标时间信息
        exif_dict = {
            'Exif.Image.DateTime': formatted_time,
            'Exif.Photo.DateTimeOriginal': formatted_time,
            'Exif.Photo.DateTimeDigitized': formatted_time
        }
        iptc_dict = {
            'Iptc.Application2.DateCreated': formatted_time
        }
        xmp_dict = {
            'Xmp.xmp.ModifyDate': formatted_time,
            'Xmp.xmp.CreateDate': formatted_time,
            'Xmp.xmp.MetadataDate': formatted_time,
            'Xmp.photoshop.DateCreated': formatted_time
        }
        # 修改EXIF、IPTC、XMP信息
        img.modify_exif(exif_dict)
        img.modify_iptc(iptc_dict)
        img.modify_xmp(xmp_dict)
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        files = [file for file in path.rglob("*.*")]
        for file in files:
            image_path = file._raw_paths[0]
            file_name = Path(image_path).stem
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
                    # 当拍摄时间年月不等于所在目录时，为照片的数据在移动过程中错误，修改年份和月份，当缺失exif数据时添加
                    if time_obj.year != parent_year or time_obj.month != parent_month or image_path in EXIF_EMPTY:
                        time_obj = datetime(parent_year, parent_month, time_obj.day, time_obj.hour, time_obj.minute, time_obj.second)
                        if file_suffix in ['.JPG', '.DNG']:
                            set_exif_data(image_path, time_obj)
                        elif file_suffix in ['.PNG']:
                            set_XML_data(image_path, time_obj)
                formatted_time = time_obj.strftime('%Y_%m_%d_%H_%M_%S')
                image_parent_path = file.parent._raw_paths[0]
                new_path = f"{image_parent_path}\\{formatted_time}_{file.name}"
                # 照片不为年_月_日_时_分_才更名
                if re.match(r'^\d{4}\_(\d{2}_){5}', file.name):
                    # new_path = image_path
                    pass
                else:
                    new_image_name = f"{formatted_time}_{file.name}"
                    new_image_path = f"{image_parent_path}\\{new_image_name}"
                    os.rename(image_path, new_image_path)
                    # 更新字典路径
                    if file_name in HEIC_DICT:
                        if file_suffix in ['.HEIC']:
                            HEIC_DICT[file_name]['heic_name'] = new_image_name
                        elif file_suffix in ['.MOV']:
                            HEIC_DICT[file_name]['mov_name'] = new_image_name
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
                    # 关闭文件
                    win32file.CloseHandle(handle)

                if file_name in HEIC_DICT and file_suffix in ['.MOV']:
                    try:
                        heic_name = HEIC_DICT[file_name]['heic_name']
                        mov_name = HEIC_DICT[file_name]['mov_name']
                        heic_path = f"{image_parent_path}\\{heic_name}"
                        mov_path = f"{image_parent_path}\\{mov_name}"
                        if re.match(r'^\d{6}\_\_$', parent_name):
                            if os.path.isfile(heic_path) and os.path.isfile(mov_path):
                                move_path = f"{image_parent_path.replace(parent_name, "实况照片")}\\{parent_name}"
                                direct_path = Path(move_path)
                                if not direct_path.is_dir():
                                    os.makedirs(direct_path, exist_ok=True)
                                os.rename(heic_path, f"{move_path}\\{heic_name}")
                                os.rename(mov_path, f"{move_path}\\{mov_name}")
                                if not os.listdir(image_parent_path):
                                    shutil.rmtree(image_parent_path)
                                    print(f"空文件夹 {image_parent_path} 已被删除")
                    except Exception as e:
                        print(f"Error: {e}")
                        print(f"移动{file_name}到新目录失败")
            else:
                print(f"{image_path}无拍摄日期")
