import configparser
import json
import logging
import ccxt
import func


# 交易所
class Exchange:
    symbol = ""
    exchange = ""

    def __init__(self):
        cf = configparser.ConfigParser()
        conf_file_name = "config.ini"
        cf.read(conf_file_name)

        exchange_name = cf.get("all", "exchange_name")
        self.exchange = ccxt.huobipro({
            'apiKey': cf.get(exchange_name, "api_key"),
            'secret': cf.get(exchange_name, "api_secret"),
        })
        self.symbol = cf.get("all", "symbol")

        # 设置市价买入允许
        # self.exchange.options["createMarketBuyOrderRequiresPrice"] = False
        pass

    # 获取指定交易对信息
    def fetch_markets(self):
        '''
        {'id': 'trxusdt', 'symbol': 'TRX/USDT', 'base': 'TRX', 'quote': 'USDT', 'baseId': 'trx', 'quoteId': 'usdt', 'active': True, 'precision': {'amount': 2, 'price': 6, 'cost': 8}, 'taker': 0.002, 'maker': 0.002, 'limits': {'amount': {'min': 1.0, 'max': 38000000.0}, 'price': {'min': 1e-06, 'max': None}, 'cost': {'min': 5.0, 'max': None}}, 'info': {'base-currency': 'trx', 'quote-currency': 'usdt', 'price-precision': '6', 'amount-precision': '2', 'symbol-partition': 'main', 'symbol': 'trxusdt', 'state': 'online', 'value-precision': '8', 'min-order-amt': '1', 'max-order-amt': '38000000', 'min-order-value': '5', 'limit-order-min-order-amt': '1', 'limit-order-max-order-amt': '38000000', 'limit-order-max-buy-amt': '38000000', 'limit-order-max-sell-amt': '38000000', 'sell-market-min-order-amt': '1', 'sell-market-max-order-amt': '3800000', 'buy-market-max-order-value': '100000', 'leverage-ratio': '5', 'super-margin-leverage-ratio': '3', 'api-trading': 'enabled', 'tags': 'activities'}}
        '''
        try:
            data = self.exchange.fetch_markets()
            for v in data:
                if v.get("symbol") == self.symbol:
                    return v
            pass
        except Exception as e:
            func.trace_log("获取指定交易对信息失败，" + str(e), "error")
        return

    # 获取订单信息
    def fetch_ticker(self):
        try:
            return self.exchange.fetch_ticker(self.symbol)['last']
        except Exception as e:
            func.trace_log("获取订单信息失败，" + str(e), "error")
        return 0

    # 获取余额
    def fetch_balance(self):
        try:
            return self.exchange.fetch_balance()
        except Exception as e:
            func.trace_log("获取余额失败，" + str(e), "error")
        return

    # 创建订单
    def create_order(self, order_type, order_side, order_amount, order_price=None):
        try:
            return self.exchange.create_order(self.symbol, order_type, order_side, order_amount, order_price)
        except Exception as e:
            func.trace_log("创建订单失败，" + str(e), "error")
        return

    # 获取订单信息
    def fetch_order(self, order_id):
        try:
            return self.exchange.fetch_order(order_id, self.symbol)
        except Exception as e:
            func.trace_log("创建订单失败，" + str(e), "error")

        return

    # 获取订单状态
    def fetch_order_status(self, order_id):
        try:
            return self.exchange.fetch_order_status(order_id, self.symbol)
        except Exception as e:
            func.trace_log("创建订单失败，" + str(e), "error")

        return

    # 批量撤销所有订单
    def batch_cancel_open_orders(self):
        try:
            return self.exchange.cancel_all_orders(self.symbol)
        except Exception as e:
            func.trace_log("批量撤销所有订单失败，" + str(e), "error")

        return

    # 获取成交明细
    def fetch_order_trades(self, order_id):
        try:
            # [{'id': '312859507982378',
            #   'info': {'symbol': 'trxusdt', 'fee-currency': 'trx', 'source': 'spot-api', 'match-id': '107271058164',
            #            'role': 'taker', 'price': '0.059253', 'created-at': '1626339343866',
            #            'order-id': '320917647469696', 'fee-deduct-state': 'done', 'trade-id': '100594126634',
            #            'filled-amount': '313.78', 'filled-fees': '0.62756', 'filled-points': '0.0',
            #            'fee-deduct-currency': '', 'id': '312859507982378', 'type': 'buy-limit'},
            #   'order': '320917647469696', 'timestamp': 1626339343866, 'datetime': '2021-07-15T08:55:43.866Z',
            #   'symbol': 'TRX/USDT', 'type': 'limit', 'side': 'buy', 'takerOrMaker': 'taker', 'price': 0.059253,
            #   'amount': 313.78, 'cost': 18.59240634, 'fee': {'cost': 0.62756, 'currency': 'TRX'}}]

            return self.exchange.fetch_order_trades(order_id)
        except Exception as e:
            func.trace_log("获取成交明细失败，" + str(e), "error")

        return
