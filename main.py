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

# results = func.get_all_order(conn)
# for row in results:
#     print(row)
# exit()
"""
下单模式：
（1）用户自定义下单
用户可自行设置区间最高价、区间最低价、网格数量、投入金额等参数，设置完成后，点击生成策略，系统会为您自动下单、交易。

（2）智能推荐设置
系统会根据历史回测数据，选择最优策略参数填入，用户仅需设置投入数额即可。
注：7日网格年化回测、单网格收益等数据均为通过历史数据进行回测，并不代表您未来的收益。

名词解释：
区间最高价：下单价格上限，当价格超过区间最高价，系统将不再执行网格区间外的下单操作（区间最高价需大于区间最低价）；
区间最低价：下单价格下限，当价格低于区间最低价，系统将不再执行网格区间外的下单操作（区间最低价应小于区间最高价）；
网格数量：将区间最高价与最低价之间分为相应等份，当价格达到时，进行下单；
投入数额：用户将在网格策略中投入的数字资产数量；
止盈价：当价格上涨至某一价格后自动停止策略，系统会将通过策略买入的基础币种卖出为计价币种，划转至币币账户中。（止盈价应高于区间最高格）；
止损价：当价格下跌至某一价格后自动停止策略，系统会将通过策略买入的基础币种卖出为计价币种，划转至币币账户中。（止损价应低于区间最低价）；
单网格利润率(%)：用户设置参数后，通过历史数据回测，计算出每个网格将会产生的收益。（（卖出价格*（1-用户币币手续费率）-买入价格/（1-用户币币手续费率））/（买入价格/（1-用户币币手续费率））；
7日网格年化回测：用户所填参数预期的年化收益能力。通过历史7日K线数据，按照所填参数计算收益，并通过“历史7日产生收益/7*365”计算得出。

以BTC/USDT交易对为例，设置参数为：
区间最高价：20700 USDT
区间最低价：19500 USDT
网格数量：7
投入金额：10000 USDT
策略创建时BTC/USDT价格为：20000 USDT

可参照下图，生成策略后，系统会以当前价格进行建仓，同时在所有格子点上挂出相应的买单和卖单（大于当前价格挂卖单，小于等于当前价格挂买单）。
当价格下跌至19700 USDT时，买单成交，并同时在19900 USDT挂出卖单。当价格继续下跌后回调至19700 USDT时，卖单成交，并在19500 USDT挂出买单，以此实现“低买高卖，高抛低吸“。
当价格涨破20700 USDT或跌破19500 USDT时，策略会暂停。当价格剧烈下跌时，建议您养成设置止损价格的习惯，防止单边下跌行情对您造成不可挽回的损失。

首次建仓位置很重要
根据这只股票或基金当前价位所处于箱体的什么位置，来测算仓位的比例。一般情况下，越贴近顶部，仓位越轻；越靠近底部，仓位越高。比如，当前价2.49元，基本上处于箱体的中部，仓位可以在可用资金的50%左右
要投入20万资金，总分网格为20格，每格分得10000元，当前价位在最高位往下数第4格位置，则首次建仓资金：10000 X 4 =4万。
"""


def main():
    try:
        # 获取当前价，判断购买的仓位比例，比如当前价格在网格的1/5位置
        grid_max_price = cf.getfloat("all", "grid_max_price")  # 网格最大值
        grid_min_price = cf.getfloat("all", "grid_min_price")  # 网格最小值
        grid_num = cf.getint("all", "grid_num")  # 网格数量
        grid_money = cf.getint("all", "grid_money")  # 投资金额
        if grid_num < 2:
            func.trace_log("设置的网格数量必须大于2" + str(grid_num), "error")
            return

        if grid_min_price >= grid_max_price:
            func.trace_log("设置的网格最小值不能大于最大值" + json.dumps([grid_min_price, grid_max_price]), "error")
            return

        if grid_money <= 0:
            func.trace_log("设置的网格购买金额太小，无意义" + str(grid_money), "error")
            return

        # 初始化
        ex = exchange.Exchange()
        # 交易对基础信息，比如TRX=5
        market_symbol_info = ex.fetch_markets()
        if market_symbol_info is None:
            func.trace_log("获取交易对异常，系统错误", "error")
            return

        # 交易对基础币种计数精度（小数点后位数），限价买入、限价卖出、市价卖出数量使用
        price_precision = int(market_symbol_info.get("info").get("price-precision"))
        # 交易对限价单和市价买单最小下单金额 ，以计价币种为单位
        min_order_value = float(market_symbol_info.get("info").get("min-order-value"))
        # 交易对限价单最小下单量 ，以基础币种为单位（NEW）
        min_order_amt = float(market_symbol_info.get("info").get("limit-order-min-order-amt"))
        func.trace_log(f"""精度:{price_precision}, 最小下注数量:{min_order_amt}, 最小下注金额:{min_order_value}""")

        # （10000 - 5000)/(6-1) = 1000
        step = round(float((grid_max_price - grid_min_price) / (grid_num - 1)), price_precision)
        func.trace_log("网格区间范围和步长" + json.dumps([grid_min_price, grid_max_price, grid_num - 1, step]))

        # 组装网格，至少2个格子
        grid_list = []
        total_price = 0
        for i in range(grid_num):
            tmp_price = grid_min_price + step * i
            if tmp_price > grid_max_price:
                tmp_price = grid_max_price
            grid_list.append(round(tmp_price, price_precision))
            total_price += round(tmp_price, price_precision)
        func.trace_log("新网格价格" + json.dumps(grid_list))

        # 计算每个格子挂单数量，总投入金额 / 格子价格总价值
        one_grid_amount = round(grid_money / total_price, price_precision)
        func.trace_log("投入金额，单网格挂单数量" + json.dumps([grid_money, one_grid_amount]))

        # 同时对最小投入金额做了限定
        if grid_money < grid_num * min_order_value:
            func.trace_log("最少投入金额必须超过" + str(grid_num * min_order_value), "error")
            return

        # 如果单笔下注金额小于最小设定金额也不允许
        if one_grid_amount < min_order_amt:
            func.trace_log("单笔下注数量小于最小设定数量不允许" + json.dumps([one_grid_amount, min_order_value]), "error")
            return

        # 获取当前价格
        now_price = ex.fetch_ticker()
        func.trace_log("当前实时价格" + str(now_price))
        if now_price <= 0:
            func.trace_log("价格获取失败" + str(now_price), "error")
            return

        if now_price > grid_max_price or now_price < grid_min_price:
            func.trace_log("网格范围设置不满足" + json.dumps([now_price, grid_min_price, grid_max_price]), "error")
            return

        # 计算当前用户的初始建仓数量
        num = 0
        for cur_price in grid_list:
            # 这里校验下，如果购买单价*数量<限制最小购买金额则提示
            if cur_price * one_grid_amount < min_order_value:
                func.trace_log("网格投入金额太少，单网格不满足最低价，" + str(cur_price * one_grid_amount), "error")
                return

            # 表示购买比例
            if now_price < cur_price:
                break
            num += 1

        # 购买份额
        func.trace_log("首次挂单，购买多少份:" + str(grid_num - num))

        # 首次挂单购买总数量
        first_buy_price = round(now_price * 1.005, price_precision)
        buy_num = one_grid_amount * (grid_num - num)
        func.trace_log("首次挂单，挂单价格和数量" + json.dumps([first_buy_price, buy_num]))

        # 读取当前数据库状态
        project_config = func.get_config(conn)

        # 下单
        if project_config is None or project_config[1] == 0:
            take_order = ex.create_order("limit", "buy", buy_num, first_buy_price)
            # take_order = ex.create_order("market", "buy", buy_num)
            if take_order is None:
                func.trace_log("首次挂单失败")
                return

            func.trace_log("首次挂单信息:" + json.dumps(take_order))

            #  确认购买订单之后，开始挂单
            while True:
                order_status = ex.fetch_order_status(take_order['id'])
                func.trace_log("首次下单数据，订单状态"+order_status)
                if order_status == "closed":
                    func.add_config(conn, 1)
                    project_config = func.get_config(conn)
                    func.trace_log("首次挂单已全部交易成功")

                    break
                time.sleep(0.5)

        if project_config is None:
            func.trace_log("首次下单数据异常，请重试", "error")
            pass

        # 开始挂买单和卖单
        if project_config[1] == 1:
            func.trace_log("--->挂网格开始<---")
            num = 0
            for cur_price in grid_list:
                func.trace_log(f"""轮询挂单，现价{now_price}:，挂单价{cur_price}:，挂单数量{one_grid_amount}""")
                # 表示购买比例
                if cur_price > now_price:
                    # 里面挂卖单
                    take_order = ex.create_order("limit", "sell", one_grid_amount, cur_price)
                    if take_order is None:
                        func.trace_log("[sell]初始下单失败," + json.dumps([one_grid_amount, cur_price]))
                        return

                    func.trace_log("[sell]下单信息:" + json.dumps(take_order))
                    # 写入数据库
                    func.create_order(conn, take_order['id'], "sell", cur_price, one_grid_amount, num + 1)
                    pass
                else:
                    # 外面挂买单
                    take_order = ex.create_order("limit", "buy", one_grid_amount, cur_price)
                    if take_order is None:
                        func.trace_log("[buy]初始下单失败," + json.dumps([one_grid_amount, cur_price]))
                        return

                    func.trace_log("[buy]下单信息:" + json.dumps(take_order))
                    # 写入数据库
                    func.create_order(conn, take_order['id'], "buy", cur_price, one_grid_amount, num + 1)
                # add++
                num += 1

            # 设置数据库状态
            project_config[1] = 2
            func.add_config(conn, 2)

        # 单子都挂好了，下一步就是开始轮询，监控每一笔订单，如果当前单子成交了，则根据当前单子的类型，决定挂上线还是下线
        if project_config[1] == 2:
            while True:
                # 实时读取配置，如果已关闭策略则进行相关动作
                cf.read(conf_file_name)
                if cf.getboolean("setting", "is_close"):
                    close_process(ex)
                    break

                results = func.get_all_order(conn)
                for row in results:
                    # 业务处理层
                    order_check_in(ex, row, one_grid_amount, grid_list)
                    time.sleep(5)
    except Exception as e:
        # func.trace_log("主进程异常退出，" + str(e))
        func.trace_log("主进程异常退出，" + str(traceback.print_exc()))


# 订单业务逻辑
def order_check_in(ex, row, one_grid_amount, grid_list):
    order_id = row[1]
    side = row[2]
    price = row[3]
    amount = row[4]
    line_num = row[5]

    func.trace_log(f"""监控订单状态，order_id:{order_id}, side:{side}, price:{price}, amount:{amount}""")

    # 防止服务器请求异常
    while True:
        try:
            order_status = ex.fetch_order_status(order_id)
            func.trace_log(f"""order_id:{order_id}, status:{order_status}""")
            # balance = ex.fetch_balance()
            # if balance['USDT']['free'] < 30:
            #     print("没钱了，不测试了", balance['USDT']['free'])
            break
        except Exception as e:
            func.trace_log("请求异常，1秒后重试，" + str(e), "error")
            time.sleep(1)
            continue

    # TODO 这里考虑网格跑到外面的情况

    if order_status is None:
        func.trace_log("订单状态异常" + json.dumps([order_id, order_status]), "error")
        return

    if order_status == 'closed':
        if side == "buy":
            func.trace_log('[buy]订单成交，订单ID='+order_id)

            # 越界判断
            if line_num < len(grid_list):
                cur_price = grid_list[line_num + 1 - 1]
                func.trace_log(f"""[buy]订单成交，当前格子索引:{line_num-1}，挂[sell]索引:{line_num}""")

                # 需要判断上一层有没有挂单，如果挂了，则不挂
                order_info = func.get_order_by_line(conn, line_num + 1)
                if order_info is None:
                    func.trace_log(f"""[buy]订单成交，挂[sell]价格:{cur_price}，[sell]数量:{one_grid_amount}""")
                    take_order = ex.create_order("limit", "sell", one_grid_amount, cur_price)
                    if take_order is None:
                        func.trace_log("[buy]订单成交，挂[sell]初始下单失败," + json.dumps([one_grid_amount, cur_price]))
                        return

                    func.trace_log("[buy]订单成交，挂[sell]下单返回:" + json.dumps(take_order))
                    # 写入新订单
                    func.create_order(conn, take_order['id'], "sell", cur_price, one_grid_amount, line_num + 1)
                else:
                    func.trace_log("[buy]订单成交，不需要挂上格[sell]，已存在")
            else:
                func.trace_log(f"""[buy]订单成交，越界判断，当前网格：{line_num}""")
        elif side == "sell":
            func.trace_log('[sell]订单成交，订单ID='+order_id)

            # 越界判断
            if line_num > 1:
                cur_price = grid_list[line_num - 1 - 1]
                func.trace_log(f"""[sell]订单成交，当前格子索引:{line_num-1}，挂[buy]索引:{line_num-2}""")

                # 需要判断下一层有没有挂单，如果挂了，则不挂
                order_info = func.get_order_by_line(conn, line_num - 1)
                if order_info is None:
                    func.trace_log(f"""[sell]订单成交，挂[buy]价格:{cur_price}，[buy]数量:{one_grid_amount}""")
                    take_order = ex.create_order("limit", "buy", one_grid_amount, cur_price)
                    if take_order is None:
                        func.trace_log("[sell]订单成交，挂[buy]初始下单失败," + json.dumps([one_grid_amount, cur_price]))
                        return

                    func.trace_log("[sell]订单成交，挂[buy]下单返回:" + json.dumps(take_order))
                    # 写入新订单
                    func.create_order(conn, take_order['id'], "buy", cur_price, one_grid_amount, line_num - 1)
                else:
                    func.trace_log("[sell]订单成交，不需要挂下格[buy]，已存在")
            else:
                func.trace_log(f"""[sell]订单成交，越界判断，当前网格：{line_num}""")

        # 删除旧订单
        func.del_order(conn, order_id)
    elif order_status == 'canceled':
        # 删除旧订单
        func.del_order(conn, order_id)


# 关闭程序，完成清理工作
def close_process(ex):
    func.trace_log("关闭程序，完成清理工作")

    # 取消全部挂单
    ex.batch_cancel_open_orders()

    # 清空数据库订单表
    func.del_all_order(conn)
    func.del_config(conn)
    pass


if __name__ == "__main__":
    main()
