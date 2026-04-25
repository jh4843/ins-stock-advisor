import pyqtgraph as pg
from PyQt6 import QtCore


# Y축 가격 표시를 위한 커스텀 축 클래스
class PriceAxis(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        return [f"{int(value):,}" for value in values]


class StockChart(pg.PlotWidget):
    def __init__(self):
        price_axis = PriceAxis(orientation="left")
        super().__init__(axisItems={"left": price_axis})

        self.setBackground("#1e1e1e")
        self.showGrid(x=True, y=True, alpha=0.3)
        self.setLabel("left", "가격", units="원")
        self.setLabel("bottom", "시간/날짜")

    def update_chart(self, df):
        self.clear()
        if df.empty:
            return

        # --- 에러 해결: 'time' 컬럼이 있는지 확인하고 안전하게 문자열 생성 ---
        if "time" in df.columns:
            date_strings = df["date"].astype(str) + " " + df["time"].astype(str)
        else:
            date_strings = df["date"].astype(str)

        x_dict = dict(enumerate(date_strings))

        # 틱(눈금) 간격 계산 시 0으로 나누어지는 오류 방지 (최소 1)
        step = max(1, len(df) // 5)
        ticks = [(i, list(x_dict.values())[i]) for i in range(0, len(df), step)]
        self.getAxis("bottom").setTicks([ticks])

        # 종가 선 그래프
        self.plot(df.index, df["close"], pen=pg.mkPen("w", width=2), name="종가")

        # 볼린저밴드 처리
        upper_col = [c for c in df.columns if c.startswith("BBU_")]
        lower_col = [c for c in df.columns if c.startswith("BBL_")]
        mid_col = [c for c in df.columns if c.startswith("BBM_")]

        if upper_col and lower_col:
            self.plot(
                df.index,
                df[upper_col[0]],
                pen=pg.mkPen("y", width=1, style=QtCore.Qt.PenStyle.DashLine),
            )
            self.plot(
                df.index,
                df[lower_col[0]],
                pen=pg.mkPen("y", width=1, style=QtCore.Qt.PenStyle.DashLine),
            )
            if mid_col:
                self.plot(
                    df.index,
                    df[mid_col[0]],
                    pen=pg.mkPen(color=(100, 100, 100), width=0.8),
                )
