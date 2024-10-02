import sqlite3
from pathlib import Path

conn = None
cursor = None

def init():
    global conn, cursor
    # 连接到 SQLite 数据库
    # 数据库文件是 mydb.db，如果文件不存在，会自动在当前目录创建
    conn = sqlite3.connect('md5.db')
    # 创建一个 Cursor 对象，通过它来执行 SQL 命令
    cursor = conn.cursor()
    # 创建一个表
    cursor.execute('''CREATE TABLE IF NOT EXISTS md5_stocks
        (md5, earliest_time, file_name, file_path, status)''')
    return
def operation(_time, _md5, _lists):
    """
    数据库操作
    :param _time: 最早的时间
    :param _md5: md5值
    :param _lists: 相同文件对应的列表
    """
    if not conn or not cursor:
        init()
    # SQL 插入语句，使用 ? 作为参数占位符
    insert_stmt = "INSERT INTO md5_stocks (md5, earliest_time, file_name, file_path, status) VALUES (?, ?, ?, ?, ?)"
    for _list in _lists:
        query(_md5)
        # 插入一行记录
        data = (_md5, _time, Path(_list).name, _list, 1)
        # 执行插入操作
        cursor.execute(insert_stmt, data)
    # 提交事务
    conn.commit()
    return

def query(_md5):
    # 执行SQL查询
    cursor.execute("SELECT * FROM md5_stocks WHERE md5 = ?", (_md5,))

    # 获取查询结果
    results = cursor.fetchall()

    for row in results:
        print(row)
    return

def destory():
    # 关闭连接
    cursor.close()
    conn.close()
    return




# # 插入一行记录
# cursor.execute("INSERT INTO md5_stocks VALUES ('2024-06-11','BUY','RHAT',100,35.14)")

# # 提交事务
# conn.commit()


# # 查询所有行
# cursor.execute('SELECT * FROM md5_stocks')
# # 获取一条记录
# stock = cursor.fetchone()
# print(stock)

# # # 执行SQL查询
# cursor.execute("SELECT * FROM md5_stocks")

# # 获取查询结果
# results = cursor.fetchall()

# for row in results:
#     print(row)

