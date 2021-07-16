import sys
from PyQt5 import QtCore, QtGui, QtWidgets
from grid_ui import Ui_MainWindow

import configparser
import json
import logging
import time
import sqlite3
import exchange
import ccxt
import func
import traceback

# 使用 cursor() 方法创建一个游标对象 cursor
conn = sqlite3.connect('orders.db')
func.init_db(conn)

tm = time.strftime('%Y%m%d', time.localtime(time.time()))
log_name = tm + '_huobi.log'
format_line = '%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s'
logging.basicConfig(filename=log_name, level=logging.INFO, format=format_line)

cf = configparser.ConfigParser()
conf_file_name = "config.ini"

# 初始化配置
func.init_config_value(cf, conf_file_name)
cf.read(conf_file_name)


class MyMainForm(QtWidgets.QMainWindow):
    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowIcon(QtGui.QIcon('favicon(blinklist_icon).ico'))

        # 读取配置，设置默认值
        self.grid_max_price = cf.get("all", "grid_max_price")
        self.grid_min_price = cf.get("all", "grid_min_price")
        self.grid_num = cf.get("all", "grid_num")
        self.grid_money = cf.get("all", "grid_money")
        self.ex = ""

        self.ui.grid_max_price.setText(self.grid_max_price)
        self.ui.grid_min_price.setText(self.grid_min_price)
        self.ui.grid_num.setText(self.grid_num)
        self.ui.grid_money.setText(self.grid_money)

        self.exchange_name = cf.get("all", "exchange_name")
        if self.exchange_name == "huobi":
            self.ui.exchange_name_list.setCurrentIndex(0)
        elif self.exchange_name == "okex":
            self.ui.exchange_name_list.setCurrentIndex(1)
        else:
            self.ui.exchange_name_list.setCurrentIndex(2)

        self.symbol = cf.get("all", "symbol")
        self.ui.symbol_list.setCurrentIndex(2)
        if self.symbol == "BTC/USDT":
            self.ui.symbol_list.setCurrentIndex(0)
        elif self.symbol == "ETH/USDT":
            self.ui.symbol_list.setCurrentIndex(1)
        elif self.symbol == "TRX/USDT":
            self.ui.symbol_list.setCurrentIndex(2)

        # 给button 的 点击动作绑定一个事件处理函数
        self.ui.stop_btn.setDisabled(True)
        self.ui.create_btn.clicked.connect(self.create_grid)
        self.ui.stop_btn.clicked.connect(self.stop_grid)

    def save_setting(self):
        # 读取用户配置并写入config.ini
        self.exchange_name = self.ui.exchange_name_list.currentText()
        self.symbol = self.ui.symbol_list.currentText()
        self.grid_max_price = self.ui.grid_max_price.text()
        self.grid_min_price = self.ui.grid_min_price.text()
        self.grid_num = self.ui.grid_num.text()
        self.grid_money = self.ui.grid_money.text()

        cf.read(conf_file_name)
        cf.set("all", "exchange_name", self.exchange_name)
        cf.set("all", "symbol", self.symbol.upper())
        cf.set("all", "grid_max_price", self.grid_max_price)
        cf.set("all", "grid_min_price", self.grid_min_price)
        cf.set("all", "grid_num", self.grid_num)
        cf.set("all", "grid_money", self.grid_money)
        with open(conf_file_name, "w+") as f:
            cf.write(f)
        pass

    # 创建网格
    def create_grid(self):
        self.ui.create_btn.setText("策略执行中...")
        self.ui.create_btn.setDisabled(True)
        self.ui.stop_btn.setDisabled(False)

        # 读取用户配置并写入config.ini
        self.save_setting()

        # 执行主逻辑
        self.main()

    # 关闭网格
    def stop_grid(self):
        self.ui.create_btn.setText("创建策略")
        self.ui.create_btn.setDisabled(False)
        self.ui.stop_btn.setDisabled(True)

        # 执行关闭
        self.close_process()
        pass

    def trace_log(self, msg, level=None):
        self.ui.textBrowser.append(msg)
        func.trace_log(msg, level)

    # 核心逻辑
    def main(self):
        try:
            # 获取当前价，判断购买的仓位比例，比如当前价格在网格的1/5位置
            grid_max_price = cf.getfloat("all", "grid_max_price")  # 网格最大值
            grid_min_price = cf.getfloat("all", "grid_min_price")  # 网格最小值
            grid_num = cf.getint("all", "grid_num")  # 网格数量
            grid_money = cf.getint("all", "grid_money")  # 投资金额
            if grid_num < 2:
                self.trace_log("设置的网格数量必须大于2" + str(grid_num), "error")
                return

            if grid_min_price >= grid_max_price:
                self.trace_log("设置的网格最小值不能大于最大值" + json.dumps([grid_min_price, grid_max_price]), "error")
                return

            if grid_money <= 0:
                self.trace_log("设置的网格购买金额太小，无意义" + str(grid_money), "error")
                return

            # 初始化
            ex = exchange.Exchange()
            self.ex = ex
            # 交易对基础信息，比如TRX=5
            market_symbol_info = ex.fetch_markets()
            if market_symbol_info is None:
                self.trace_log("获取交易对异常，系统错误", "error")
                return

            # 交易对基础币种计数精度（小数点后位数），限价买入、限价卖出、市价卖出数量使用
            price_precision = int(market_symbol_info.get("info").get("price-precision"))
            # 交易数额精度错误
            amount_precision = int(market_symbol_info.get("info").get("amount-precision"))
            # 交易对限价单和市价买单最小下单金额 ，以计价币种为单位
            min_order_value = float(market_symbol_info.get("info").get("min-order-value"))
            # 交易对限价单最小下单量 ，以基础币种为单位（NEW）
            min_order_amt = float(market_symbol_info.get("info").get("limit-order-min-order-amt"))
            self.trace_log(f"""价格精度:{price_precision}, 数量精度:{amount_precision}, 最小下注:{min_order_amt}, 最小金额:{min_order_value}""")

            # （10000 - 5000)/(6-1) = 1000
            step = func.round_down(float((grid_max_price - grid_min_price) / (grid_num - 1)), price_precision)
            self.trace_log("网格区间范围和单格价差" + json.dumps([grid_min_price, grid_max_price, grid_num - 1, step]))

            # 组装网格，至少2个格子
            grid_list = []
            total_price = 0
            for i in range(grid_num):
                tmp_price = grid_min_price + step * i
                if tmp_price > grid_max_price:
                    tmp_price = grid_max_price
                grid_list.append(func.round_down(tmp_price, price_precision))
                total_price += func.round_down(tmp_price, price_precision)
            self.trace_log("新网格价格" + json.dumps(grid_list))

            # 计算每个格子挂单数量，总投入金额 / 格子价格总价值
            one_grid_amount = func.round_down(grid_money / total_price, amount_precision)
            self.trace_log("投入金额，单网格挂单数量" + json.dumps([grid_money, one_grid_amount]))

            # 同时对最小投入金额做了限定
            if grid_money < grid_num * min_order_value:
                self.trace_log("最少投入金额必须超过" + str(grid_num * min_order_value), "error")
                return

            # 如果单笔下注金额小于最小设定金额也不允许
            if one_grid_amount < min_order_amt:
                self.trace_log("单笔下注数量小于最小设定数量不允许" + json.dumps([one_grid_amount, min_order_value]), "error")
                return

            # 获取当前价格
            now_price = ex.fetch_ticker()
            self.trace_log("当前实时价格" + str(now_price))
            if now_price <= 0:
                self.trace_log("价格获取失败" + str(now_price), "error")
                return

            if now_price > grid_max_price or now_price < grid_min_price:
                self.trace_log("网格范围设置不满足" + json.dumps([now_price, grid_min_price, grid_max_price]), "error")
                return

            # 计算当前用户的初始建仓数量
            num = 0
            for cur_price in grid_list:
                # 这里校验下，如果购买单价*数量<限制最小购买金额则提示
                if cur_price * one_grid_amount < min_order_value:
                    self.trace_log("网格投入金额太少，单网格不满足最低价，" + str(cur_price * one_grid_amount), "error")
                    return

                # 表示购买比例
                if now_price < cur_price:
                    break
                num += 1

            # 购买份额
            self.trace_log("首次挂单，购买多少份:" + str(grid_num - num))

            # 首次挂单购买总数量
            first_buy_price = func.round_down(now_price * 1.005, price_precision)
            buy_num = one_grid_amount * (grid_num - num)
            self.trace_log("首次挂单，挂单价格和数量" + json.dumps([first_buy_price, buy_num]))

            # 读取当前数据库状态
            project_config = func.get_config(conn)

            # 下单
            if project_config is None or project_config[1] == 0:
                take_order = ex.create_order("limit", "buy", buy_num, first_buy_price)
                # take_order = ex.create_order("market", "buy", buy_num)
                if take_order is None:
                    self.trace_log("首次挂单失败")
                    return

                self.trace_log("首次挂单信息:" + json.dumps(take_order))

                #  确认购买订单之后，开始挂单
                while True:
                    first_order_info = ex.fetch_order(take_order['id'])
                    self.trace_log("首次下单数据，订单返回信息："+json.dumps(first_order_info))
                    if first_order_info is not None and first_order_info.get("status") == "closed":
                        # 顺便计算当前买币手续费
                        buy_fee_rate = float(first_order_info.get("fee").get("cost") / first_order_info.get("amount"))

                        func.add_config(conn, 1, buy_fee_rate)
                        self.trace_log("首次挂单已全部交易成功")
                        break
                    time.sleep(0.5)

            if project_config is None:
                self.trace_log("首次下单数据异常，请重试", "error")
                pass

            # 兼容修改，fix tuple not update
            project_config = func.get_config(conn)
            is_run_step = project_config[1]
            buy_fee_rate = project_config[2]

            # 开始挂买单和卖单
            if is_run_step == 1:
                self.trace_log("--->挂网格开始<---")
                num = 0
                for cur_price in grid_list:
                    if cur_price > now_price:
                        # 里面挂卖单
                        tmp_one_grid_amount = func.round_down(one_grid_amount * (1-buy_fee_rate), amount_precision)  # 扣手续费
                        self.trace_log(f"""轮询挂[sell]单，现价{now_price}:，挂单价{cur_price}:，计划挂单数量{tmp_one_grid_amount}""")
                        take_order = ex.create_order("limit", "sell", tmp_one_grid_amount, cur_price)
                        if take_order is None:
                            self.trace_log("[sell]初始下单失败," + json.dumps([tmp_one_grid_amount, cur_price]))
                            return

                        self.trace_log("[sell]下单信息:" + json.dumps(take_order))
                        # 写入数据库
                        func.create_order(conn, take_order['id'], "sell", cur_price, tmp_one_grid_amount, num + 1)
                        pass
                    else:
                        # 外面挂买单
                        self.trace_log(f"""轮询挂[buy]单，现价{now_price}:，挂单价{cur_price}:，计划挂单数量{one_grid_amount}""")
                        take_order = ex.create_order("limit", "buy", one_grid_amount, cur_price)
                        if take_order is None:
                            self.trace_log("[buy]初始下单失败," + json.dumps([one_grid_amount, cur_price]))
                            return

                        self.trace_log("[buy]下单信息:" + json.dumps(take_order))
                        # 写入数据库
                        func.create_order(conn, take_order['id'], "buy", cur_price, one_grid_amount, num + 1)
                    # add++ 累加计数
                    num += 1

                # 设置config运行状态
                func.add_config(conn, 2, buy_fee_rate)
                is_run_step = 2

            # 单子都挂好了，下一步就是开始轮询，监控每一笔订单，如果当前单子成交了，则根据当前单子的类型，决定挂上线还是下线
            if is_run_step == 2:
                while True:
                    # 实时读取配置，如果已关闭策略则进行相关动作
                    cf.read(conf_file_name)
                    if cf.getboolean("setting", "is_close"):
                        self.close_process(ex)
                        break

                    results = func.get_all_order(conn)
                    for row in results:
                        # 业务处理层
                        self.order_check_in(ex, row, one_grid_amount, grid_list, buy_fee_rate, amount_precision)
                        time.sleep(5)
        except Exception as e:
            # self.trace_log("主进程异常退出，" + str(e))
            self.trace_log("主进程异常退出，" + str(traceback.print_exc()))

    # 订单业务逻辑
    def order_check_in(self, ex, row, one_grid_amount, grid_list, buy_fee_rate, amount_precision):
        order_id = row[1]
        side = row[2]
        price = row[3]
        amount = row[4]
        line_num = row[5]

        self.trace_log(f"""监控订单状态，order_id:{order_id}, side:{side}, price:{price}, amount:{amount}""")

        # 防止服务器请求异常
        while True:
            try:
                order_status = ex.fetch_order_status(order_id)
                self.trace_log(f"""order_id:{order_id}, status:{order_status}""")
                # balance = ex.fetch_balance()
                # if balance['USDT']['free'] < 30:
                #     print("没钱了，不测试了", balance['USDT']['free'])
                break
            except Exception as e:
                self.trace_log("请求异常，1秒后重试，" + str(e), "error")
                time.sleep(1)
                continue

        # TODO 这里考虑网格跑到外面的情况

        if order_status is None:
            self.trace_log("订单状态异常" + json.dumps([order_id, order_status]), "error")
            return

        if order_status == 'closed':
            if side == "buy":
                self.trace_log('[buy]订单成交，订单ID='+order_id)

                # 越界判断
                if line_num < len(grid_list):
                    cur_price = grid_list[line_num + 1 - 1]
                    self.trace_log(f"""[buy]订单成交，当前格子索引:{line_num-1}，挂[sell]索引:{line_num}""")

                    # 需要判断上一层有没有挂单，如果挂了，则不挂
                    order_info = func.get_order_by_line(conn, line_num + 1)
                    if order_info is None:
                        # 挂卖单需要计算手续费扣除情况
                        one_grid_amount = func.round_down(one_grid_amount * (1-buy_fee_rate), amount_precision)
                        self.trace_log(f"""[buy]订单成交，挂[sell]价格:{cur_price}，[sell]数量:{one_grid_amount}""")
                        take_order = ex.create_order("limit", "sell", one_grid_amount, cur_price)
                        if take_order is None:
                            self.trace_log("[buy]订单成交，挂[sell]初始下单失败," + json.dumps([one_grid_amount, cur_price]))
                            return

                        self.trace_log("[buy]订单成交，挂[sell]下单返回:" + json.dumps(take_order))
                        # 写入新订单
                        func.create_order(conn, take_order['id'], "sell", cur_price, one_grid_amount, line_num + 1)
                    else:
                        self.trace_log("[buy]订单成交，不需要挂上格[sell]，已存在")
                else:
                    self.trace_log(f"""[buy]订单成交，越界判断，当前网格：{line_num}""")
            elif side == "sell":
                self.trace_log('[sell]订单成交，订单ID='+order_id)

                # 越界判断
                if line_num > 1:
                    cur_price = grid_list[line_num - 1 - 1]
                    self.trace_log(f"""[sell]订单成交，当前格子索引:{line_num-1}，挂[buy]索引:{line_num-2}""")

                    # 需要判断下一层有没有挂单，如果挂了，则不挂
                    order_info = func.get_order_by_line(conn, line_num - 1)
                    if order_info is None:
                        self.trace_log(f"""[sell]订单成交，挂[buy]价格:{cur_price}，[buy]数量:{one_grid_amount}""")
                        take_order = ex.create_order("limit", "buy", one_grid_amount, cur_price)
                        if take_order is None:
                            self.trace_log("[sell]订单成交，挂[buy]初始下单失败," + json.dumps([one_grid_amount, cur_price]))
                            return

                        self.trace_log("[sell]订单成交，挂[buy]下单返回:" + json.dumps(take_order))
                        # 写入新订单
                        func.create_order(conn, take_order['id'], "buy", cur_price, one_grid_amount, line_num - 1)
                    else:
                        self.trace_log("[sell]订单成交，不需要挂下格[buy]，已存在")
                else:
                    self.trace_log(f"""[sell]订单成交，越界判断，当前网格：{line_num}""")

            # 删除旧订单
            func.del_order(conn, order_id)
        elif order_status == 'canceled':
            # 删除旧订单
            func.del_order(conn, order_id)

    # 关闭程序，完成清理工作
    def close_process(self, ex=None):
        if ex is None:
            self.trace_log("清理异常")
            return

        self.trace_log("已手动关闭挂单程序，开始清理工作")

        # 取消全部挂单
        self.ex.batch_cancel_open_orders()

        # 清空数据库订单表
        func.del_all_order(conn)
        func.del_config(conn)

        self.trace_log("清理工作，已完成")
        pass


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MyMainForm()
    window.show()
    sys.exit(app.exec_())

