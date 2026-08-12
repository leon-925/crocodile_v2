import numpy as np


def analyze(result):

    equity = result["equity"]


    total_return = (
        equity.iloc[-1]
        /
        equity.iloc[0]
        -
        1
    )


    drawdown = (
        equity
        /
        equity.cummax()
        -
        1
    )


    max_drawdown = drawdown.min()



    daily_return = (
        equity
        .pct_change()
        .dropna()
    )


    if daily_return.std()!=0:

        sharpe = (
            daily_return.mean()
            /
            daily_return.std()
            *
            np.sqrt(252)
        )

    else:

        sharpe = 0



    return {

        "总收益率":
            round(total_return*100,2),

        "最大回撤":
            round(max_drawdown*100,2),

        "夏普比率":
            round(sharpe,2)

    }