import numpy as np
import pandas as pd
from datetime import datetime



class RiskManager:
    """
    量化交易风险管理模块

    功能:
    1. 仓位控制
    2. 单笔风险控制
    3. 最大回撤控制
    4. 波动率控制
    5. 连续亏损控制
    6. 流动性控制
    7. 交易频率限制
    8. 风险评分

    """



    def __init__(
        self,
        max_position=0.2,
        max_drawdown=0.2,
        risk_per_trade=0.01,
        max_daily_trade=10,
        max_loss_count=5,
        volatility_limit=0.4
    ):


        # 单股票最大仓位
        self.max_position=max_position


        # 最大回撤
        self.max_drawdown=max_drawdown


        # 每次交易风险
        self.risk_per_trade=risk_per_trade


        # 每日交易次数
        self.max_daily_trade=max_daily_trade


        # 连续亏损次数
        self.max_loss_count=max_loss_count


        # 波动率限制
        self.volatility_limit=volatility_limit



        self.trade_count=0

        self.loss_count=0

        self.highest_equity=0



    # ===============================
    # 1. 仓位检查
    # ===============================

    def check_position(
        self,
        current_value,
        total_asset
    ):


        ratio=current_value/total_asset


        if ratio > self.max_position:

            return False,{
                "reason":
                "单股票仓位超过限制"
            }


        return True,{}



    # ===============================
    # 2. 计算交易数量
    # ===============================


    def calculate_position_size(
        self,
        capital,
        price,
        stop_loss_price
    ):


        """

        根据风险决定买多少

        """

        risk_money = (
            capital*
            self.risk_per_trade
        )


        loss_per_share=abs(
            price-stop_loss_price
        )


        if loss_per_share==0:

            return 0


        shares=int(
            risk_money/
            loss_per_share
        )


        return shares



    # ===============================
    # 3. 最大回撤控制
    # ===============================


    def check_drawdown(
        self,
        equity
    ):


        if equity>self.highest_equity:

            self.highest_equity=equity


        drawdown=(
            self.highest_equity-
            equity
        )/self.highest_equity



        if drawdown>self.max_drawdown:


            return False,{
                "reason":
                "超过最大回撤限制",
                "drawdown":
                drawdown
            }


        return True,{
            "drawdown":
            drawdown
        }



    # ===============================
    # 4. 波动率控制
    # ===============================


    def check_volatility(
        self,
        returns
    ):


        volatility=np.std(
            returns
        )*np.sqrt(252)



        if volatility > self.volatility_limit:


            return False,{
                "reason":
                "市场波动过高",
                "volatility":
                volatility
            }



        return True,{
            "volatility":
            volatility
        }




    # ===============================
    # 5. 连续亏损控制
    # ===============================


    def update_trade_result(
        self,
        profit
    ):


        if profit<0:

            self.loss_count+=1

        else:

            self.loss_count=0




    def check_loss_limit(self):


        if self.loss_count>=self.max_loss_count:


            return False,{
                "reason":
                "连续亏损过多"
            }


        return True,{}



    # ===============================
    # 6. 交易次数限制
    # ===============================


    def check_trade_frequency(self):


        if self.trade_count>=self.max_daily_trade:


            return False,{
                "reason":
                "超过每日交易次数"
            }



        return True,{}




    def update_trade_count(self):

        self.trade_count+=1



    # ===============================
    # 7. 流动性检查
    # ===============================


    def check_liquidity(
        self,
        order_value,
        avg_volume,
        price
    ):


        daily_value=(
            avg_volume*
            price
        )


        if order_value > daily_value*0.05:


            return False,{
                "reason":
                "订单超过市场流动性限制"
            }



        return True,{}




    # ===============================
    # 8. 总风险检查
    # ===============================


    def validate_order(
        self,
        order,
        portfolio,
        market_data
    ):


        checks=[]


        checks.append(
            self.check_position(
                portfolio["position_value"],
                portfolio["total_asset"]
            )
        )


        checks.append(
            self.check_drawdown(
                portfolio["equity"]
            )
        )


        checks.append(
            self.check_volatility(
                market_data["returns"]
            )
        )


        checks.append(
            self.check_loss_limit()
        )


        checks.append(
            self.check_trade_frequency()
        )



        for result,info in checks:


            if result is False:

                return {
                    "approved":False,
                    "info":info
                }



        return {
            "approved":True,
            "info":
            {
                "message":
                "risk check passed"
            }
        }



    # ===============================
    # 9. 风险评分
    # ===============================


    def risk_score(
        self,
        drawdown,
        volatility,
        position
    ):


        score=100


        score-=drawdown*100


        score-=volatility*50


        score-=position*30



        return max(
            0,
            min(
                100,
                score
            )
        )
