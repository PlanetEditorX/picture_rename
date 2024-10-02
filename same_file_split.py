import sys
import os
import time
import shutil
from pathlib import Path
import hashlib
from datetime import datetime
import main
import sq

# md5字典
MD5_DICT = {}
# 父目录
parent_path = ''

# 获取文件的md5
def get_file_md5(file_path):
    global MD5_DICT
    md5 = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:  # 以二进制读取模式打开文件
            for chunk in iter(lambda: f.read(4096), b""):  # 读取文件，每次读取4096字节
                md5.update(chunk)  # 更新MD5值
    except FileNotFoundError:
        print(f"文件 {file_path} 未找到")
        return None
    except Exception as e:
        print(f"读取文件 {file_path} 时发生错误: {e}")
        return None
    return md5.hexdigest()  # 返回十六进制的MD5值

# 存储md5字典
def set_md5_dict(file_md5, file_path):
    global MD5_DICT
    try:
        if file_md5 not in MD5_DICT:
            MD5_DICT[file_md5] = [file_path]
        else:
            MD5_DICT[file_md5].append(file_path)
    except Exception as e:
        print(f"存储文件 {file_path} md5 时发生错误: {e}")
        return None
    return None

# 移动文件
def move_file(folder_time, lists):
    try:
        folder_name = folder_time.strftime('%Y%m__')
        folder_path = f"{parent_path}\\重复文件\\{folder_name}"
        if not os.path.exists(folder_path) and not os.path.isdir(folder_path):
            os.makedirs(folder_path, exist_ok=True)
            print(f"文件夹 '{folder_path}' 创建成功。")

        for item in lists:
            # 检查源文件是否存在
            if os.path.exists(item):
                try:
                    # 移动文件
                    shutil.move(item, folder_path)
                    print(f"文件已从 '{item}' 移动到 '{folder_path}'")
                except Exception as e:
                    print(f"移动文件时出错: {e}")
            else:
                print(f"源文件 '{item}' 不存在。")

    except Exception as e:
        print(f"获取文件 {file_path} 状态信息时发生错误: {e}")
        return None
    return

def print_progress(iteration, total, prefix='', suffix='', decimals=1, length=50, fill='█'):
    """
    在命令行中打印进度条
    :param iteration: 当前迭代次数
    :param total: 总迭代次数
    :param prefix: 前缀字符串
    :param suffix: 后缀字符串
    :param decimals: 正数，显示的小数位数
    :param length: 进度条的长度
    :param fill: 填充字符
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end='')
    if iteration == total:
        print()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        parent_path = path.parent._raw_paths[0]
        files = [file for file in path.rglob("*.*")]
        index = 0  # 初始化计数器
        total = len(files)
        for file in files:
            file_path = file._raw_paths[0]
            # 绝对地址
            absolute_path = os.path.abspath(file_path)
            filemd5 = get_file_md5(absolute_path)
            set_md5_dict(filemd5, absolute_path)
            print_progress(index, total, prefix='正在计算文件MD5信息:', suffix='完成', decimals=2)
            index += 1

        print_progress(total, total, prefix='正在计算文件MD5信息:', suffix='完成', decimals=2)

        if MD5_DICT:
            index = 0  # 初始化计数器
            total = len(MD5_DICT)
            for key, value in MD5_DICT.items():
                if len(value) > 1:
                    earliest_time = main.get_time_info(value)
                    move_file(earliest_time, value)
                    sq.operation(earliest_time, key, value)
                print_progress(index, total, prefix='正在移动重复文件:', suffix='完成', decimals=2)
                index += 1
            print_progress(total, total, prefix='正在移动重复文件:', suffix='完成', decimals=2)
            sq.destory()


