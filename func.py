import time
import logging


# 初始化基础配置
def init_config_value(cf, conf_file_name):
    cf.read(conf_file_name)
    cf.set("setting", "is_close", "0")
    with open(conf_file_name, "w+") as f:
        cf.write(f)

# 输出log
def trace_log(msg, level="info"):
    print(msg)

    if level == "info":
        logging.info(msg)
    elif level == "error":
        logging.error(msg)
    elif level == "warning" or level == "warn":
        logging.warning(msg)


# 初始化数据库
def init_db(conn):
    try:
        conn.cursor().execute('''CREATE TABLE "orders" (
          "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
          "order_id" text,
          "side" TEXT,
          "price" real,
          "amount" real,
          "line_num" INTEGER,
          "create_time" INTEGER
        );''')
        conn.commit()
        print("orders 创建成功")
    except Exception as e:
        print("orders 已存在")


    try:
        conn.cursor().execute('''CREATE TABLE "config" (
          "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
          "is_run" INTEGER
        );''')
        conn.commit()
        print("config 创建成功")
    except Exception as e:
        print("config 已存在")


def create_order(conn, order_id, side, price, amount, line_num):
    create_time = int(time.time())
    conn.cursor().execute(f"""INSERT INTO orders(order_id, side, price, amount, line_num, create_time) VALUES ('{order_id}', '{side}', {price}, {amount}, {line_num}, {create_time} )""")
    conn.commit()
    pass


def del_order(conn, order_id):
    conn.cursor().execute(f"""DELETE FROM orders WHERE order_id = '{order_id}'""")
    conn.commit()
    pass


def del_all_order(conn):
    conn.cursor().execute(f"""DELETE FROM orders""")
    conn.commit()
    pass


def get_all_order(conn):
    cursor = conn.cursor()
    cursor.execute(f"""SELECT * FROM orders ORDER BY price""")
    return cursor


def get_order_by_line(conn, line_num):
    cursor = conn.cursor()
    cursor.execute(f"""SELECT * FROM orders where line_num = {line_num}""")
    return cursor.fetchone()

# num=1
def add_config(conn, num):
    if get_config(conn) is not None:
        # 更新
        sql = f"""update config set is_run = {num}"""
        pass
    else:
        sql = f"""INSERT INTO config(is_run) VALUES ({num})"""
    conn.cursor().execute(sql)
    conn.commit()
    pass


def get_config(conn):
    cursor = conn.cursor()
    cursor.execute(f"""select * from config""")
    return cursor.fetchone()


def del_config(conn):
    conn.cursor().execute(f"""DELETE FROM config""")
    conn.commit()
    pass
