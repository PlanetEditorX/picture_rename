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

# pip install pywin32
# pip install piexif
# pip install whatimage
# pip install pillow
# pip install pillow_heif
# pip install exifread
# pip install pytz
# pip install pymediainfo
# pip install pyexiv2


# 实况照片字典
HEIC_DICT = {}
# 缺失exif数据的图片
EXIF_EMPTY = []
# 忽略的文件
IGNORE_LIST = ['desktop.ini']

# 注册 HEIC 文件打开器,让Pillow 库就能够识别和打开 HEIC 格式的文件
pillow_heif.register_heif_opener()

# type: 0为图片,1为视频
def get_exif_data(path, type = 0):
    """
    获取exif数据
    :param path: 文件路径
    :param type: 文件类型（0为图片，1为视频）
    """
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
                    if not encoded_date:
                        encoded_date = getattr(track, 'file_last_modification_date', None)
                        return datetime.strptime(encoded_date, '%Y-%m-%d %H:%M:%S.%f UTC')
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
                        return find_earliest_time(track)
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
                    return find_earliest_time_file(path)
    except Exception as e:
        print(f"Error: {e}")
        return None

# 查找视频最早时间
def find_earliest_time(track):
    """
    查找视频最早时间
    :param track: 视频轨道
    """
    creation_date = getattr(track, 'file_creation_date', None)
    modification_date = getattr(track, 'file_earliest_modification_date', None)
    if creation_date:
        creation_date = datetime.strptime(creation_date, '%Y-%m-%d %H:%M:%S.%f UTC')
    if modification_date:
        modification_date = datetime.strptime(modification_date, '%Y-%m-%d %H:%M:%S.%f UTC')
    if creation_date > modification_date:
        return modification_date
    return creation_date

# 查找文件最早时间
def find_earliest_time_file(file_path):
    """
    查找文件最早时间
    :param file_path: 文件路径
    """
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
        EXIF_EMPTY.append(file_path)
        if mod_time > creation_time:
            return creation_time
        return mod_time
    except Exception as e:
        print(f"Error: {e}")
        return None

# 读取heic照片信息
def read_heic_exif(heic_path):
    """
    读取heic格式图片的时间信息
    :param heic_path: 图片路径
    """
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
def read_png_exif(image_path):
    """
    读取png格式图片的时间信息
    :param image_path: 图片路径
    """
    try:
        img = Image(image_path)
        load_exif = img.read_exif()
        if load_exif:
            # PNG未获取到通用的拍摄日期
            CreationTime = read_png_exif_more(image_path)
            return load_exif['Exif.Photo.DateTimeOriginal']
        return read_png_exif_more(image_path)
    except Exception as e:
        print(f"Warning: {image_path}默认方式未获取到时间相关数据")
        print("Trying：尝试使用其它方式读取PNG信息")
        return read_png_exif_more(image_path)

# 读取png照片信息其它方式
def read_png_exif_more(image_path):
    """
    通过其它方式读取png照片信息
    :param image_path: 图片路径
    """
    global EXIF_EMPTY
    try:
        image = PIL_Image.open(image_path)
        timetext =getattr(image, 'text' ,None)
        if timetext:
            CreationTime = timetext['Creation Time']
            return CreationTime
        else:
            EXIF_EMPTY.append(image_path)
        return None
    except Exception as e:
        print(f"Warning: {image_path}未获取到exif数据")
        EXIF_EMPTY.append(image_path)
        return None

# 读取普通照片信息
def read_image_exif(image_path):
    """
    读取普通照片EXIF的时间信息
    :param image_path: 图片路径
    """
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
    """
    读取DNG格式图片的时间信息
    :param image_path: 图片路径
    """
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
    """
    修改图片XML信息
    :param image_path: 图片路径
    :param new_time: 需要修改的时间值
    """
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
    """
    修改图片XML信息
    :param image_path: 图片路径
    :param new_time: 需要修改的时间值
    """
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

# 计算指定目录下的文件数量
def count_files(directory):
    """
    计算指定目录下的文件数量，去除忽略列表（如：desktop.ini）
    :param directory: 需要查询的目录地址
    """
    total_files = 0
    for root, dirs, files in os.walk(directory):
        total_files += len(files)
        for file in files:
            if file in IGNORE_LIST:
                total_files -= 1
    return total_files

# 删除数组的指定值
def remove_value(lst, value):
    """
    删除数组的指定值
    :param lst: 原始数组
    :param value: 需要删除的值
    """
    return list(filter(lambda x: x != value, lst))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        files = [file for file in path.rglob("*.*") if file.name not in IGNORE_LIST]
        or_num = len(files)
        print(f"开始：该目录下共找到{or_num}个文件")
        path_list = []
        path_dict = {}
        for file in files:
            image_path = file._raw_paths[0]
            file_name = Path(image_path).stem
            file_suffix = file.suffix.upper()
            time_obj = None
            if file_suffix in ['.JPG', '.PNG', '.DNG', '.HEIC']:
                time_obj = get_exif_data(image_path)
            elif file_suffix in ['.MP4', '.MOV', '.3GP']:
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
                    try:
                        new_image_name = f"{formatted_time}_{file.name}"
                        new_image_path = f"{image_parent_path}\\{new_image_name}"
                        os.rename(image_path, new_image_path)
                        # 存储新路径
                        path_list.append(new_image_path)
                        # 存储新路径对应的原始路径
                        path_dict[new_image_path] = image_path
                    except Exception as e:
                        print(f"Error: {e}")
                        print(f"移动{file_name}到新目录失败")
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

                if file_name in HEIC_DICT and file_suffix in ['.MOV'] and not re.match(r'^\d{4}\_(\d{2}_){5}', file.name):
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
                                new_heic_path = f"{move_path}\\{heic_name}"
                                new_mov_path = f"{move_path}\\{mov_name}"
                                os.rename(heic_path, new_heic_path)
                                os.rename(mov_path, new_mov_path)
                                path_list.extend([new_heic_path, new_mov_path])
                                # 列表删除被移动的原始地址
                                path_list.remove(heic_path)
                                path_list.remove(mov_path)
                                path_dict[new_heic_path] = heic_path
                                path_dict[new_mov_path] = mov_path

                                if not os.listdir(image_parent_path):
                                    shutil.rmtree(image_parent_path)
                                    print(f"空文件夹 {image_parent_path} 已被删除")
                    except Exception as e:
                        print(f"Error: {e}")
                        print(f"移动{file_name}到新目录失败")
            else:
                print(f"{image_path}无拍摄日期")

        new_num = count_files(path)
        print(f"结束：完成操作后该目录下共找到{new_num}个文件")
        if or_num == new_num:
            print("OK：操作并未造成文件数量变动")
        else:
            print("ERROR：操作完成后发现文件数量变动")
            print("正在查找丢失的源文件路径")
            new_files = [file for file in path.rglob("*.*") if file.name not in IGNORE_LIST]
            for file in new_files:
                image_path = file._raw_paths[0]
                path_list = remove_value(path_list, image_path)
            move_nums = 0
            for item in path_list:
                if os.path.exists(item):
                    print(f"文件{item}存在")
                    move_nums += 1
                else:
                    print(f"新文件{item}丢失！")
                    or_path = path_dict.get(item)
                    print(f"原始文件路径为{or_path}，请手动查找或找到副本后重新开始！")
            if or_num == new_num + move_nums:
                print("OK：操作并未造成文件实际数量变动，源文件夹不同是因为实况照片被移动到对应文件夹中。")
            else:
                print("ERROR：操作完成后发现文件数量变动，且默认移动文件夹未找到对应文件，请手动查找丢失文件！！！")



# 外部调用，返回拍摄日期或最早日期
def get_time_info(lists):
    """
    返回拍摄日期或最早日期
    :param lists: 需要查找的文件地址列表
    """
    earliest_time_obj = datetime.now()
    for file_path in lists:
        file = Path(file_path)
        file_name = file.stem
        file_suffix = file.suffix.upper()
        if file_suffix in ['.JPG', '.PNG', '.DNG', '.HEIC']:
            time_obj = get_exif_data(file_path)
        elif file_suffix in ['.MP4', '.MOV']:
            time_obj = get_exif_data(file_path, 1)
        # 非照片视频文件比较最早的时间
        else:
            time_obj = find_earliest_time_file(file_path)
        # 存储相同文件中读取到的最早信息
        if time_obj and earliest_time_obj.timestamp() > time_obj.timestamp():
            earliest_time_obj = time_obj
    return earliest_time_obj
