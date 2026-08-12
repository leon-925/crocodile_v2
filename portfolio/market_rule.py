from datetime import datetime


class MarketRule:


    def __init__(self):

        self.rules = {

            "CN":{

                "commission_rate":0.0003,
                "min_commission":5,
                "stamp_tax":0.001,
                "lot_size":100
            },


            "US":{

                "commission_rate":0,
                "min_commission":0,
                "stamp_tax":0,
                "lot_size":1
            },


            "HK":{

                "commission_rate":0.0005,
                "min_commission":5,
                "stamp_tax":0,
                "lot_size":100
            }

        }



    def get_rule(
        self,
        market
    ):

        if market not in self.rules:

            raise ValueError(
                "Unknown market"
            )


        return self.rules[market]
    def calculate_fee(
        self,
        market,
        price,
        quantity,
        side
    ):


        rule=self.get_rule(market)


        amount=price*quantity


        commission=max(
            amount*rule["commission_rate"],
            rule["min_commission"]
        )


        stamp_tax=0


        if side=="SELL":

            stamp_tax=(
                amount*
                rule["stamp_tax"]
            )


        return commission+stamp_tax