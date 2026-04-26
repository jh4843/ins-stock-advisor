import pandas as pd
import pyqtgraph as pg
from PyQt6 import QtCore


# Y축 가격 표시를 위한 커스텀 축 클래스
class PriceAxis(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        return [f"{int(value):,}" for value in values if not pd.isna(value)]


class StockChart(pg.PlotWidget):
    def __init__(self):
        price_axis = PriceAxis(orientation="left")
        super().__init__(axisItems={"left": price_axis})

        self.setBackground("#1e1e1e")
        self.showGrid(x=True, y=True, alpha=0.3)
        self.setLabel("left", "가격", units="원")
        self.setLabel("bottom", "시간/날짜")

        self.df = None
        self.date_strings = []

        # --- 👑 고급 기능: 십자선(Crosshair) 및 툴팁 UI 초기화 ---
        self.vLine = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen(color="#888888", width=1, style=QtCore.Qt.PenStyle.DashLine),
        )
        self.hLine = pg.InfiniteLine(
            angle=0,
            movable=False,
            pen=pg.mkPen(color="#888888", width=1, style=QtCore.Qt.PenStyle.DashLine),
        )
        self.addItem(self.vLine, ignoreBounds=True)
        self.addItem(self.hLine, ignoreBounds=True)

        # 툴팁 배경 및 텍스트 설정 (HTML 형태 지원)
        self.tooltip = pg.TextItem(
            anchor=(0, 1),  # 마우스 우측 하단에 위치
            fill=pg.mkBrush(20, 20, 20, 230),  # 반투명 어두운 배경
            border=pg.mkPen(color="#555555", width=1),
        )
        self.addItem(self.tooltip, ignoreBounds=True)

        self.vLine.hide()
        self.hLine.hide()
        self.tooltip.hide()

        # 마우스 이동 이벤트를 최적화해서 받기 위한 SignalProxy (초당 60프레임 제한)
        self.proxy = pg.SignalProxy(
            self.scene().sigMouseMoved, rateLimit=60, slot=self.mouse_moved
        )

    def update_chart(self, df):
        self.df = df
        self.clear()

        # clear()를 호출하면 십자선과 툴팁도 지워지므로 다시 추가해 줘요
        self.addItem(self.vLine, ignoreBounds=True)
        self.addItem(self.hLine, ignoreBounds=True)
        self.addItem(self.tooltip, ignoreBounds=True)

        if df.empty:
            return

        # 시간 정보 포함 여부에 따른 날짜 문자열 생성
        if "time" in df.columns:
            self.date_strings = (
                df["date"].astype(str) + " " + df["time"].astype(str)
            ).tolist()
        else:
            self.date_strings = df["date"].astype(str).tolist()

        x_dict = dict(enumerate(self.date_strings))

        # 틱(눈금) 간격 계산 시 0으로 나누어지는 오류 방지
        step = max(1, len(df) // 5)
        ticks = [(i, list(x_dict.values())[i]) for i in range(0, len(df), step)]
        self.getAxis("bottom").setTicks([ticks])

        # 종가 선 그래프
        self.plot(df.index, df["close"], pen=pg.mkPen("#00bfff", width=2), name="종가")

        # 볼린저밴드 처리 (pandas_ta가 만들어준 컬럼명을 동적으로 찾음)
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

    def mouse_moved(self, evt):
        pos = evt[0]  # 마우스의 화면 좌표
        # 마우스가 차트 영역 안에 있고, 데이터가 로드된 상태일 때만 동작
        if (
            self.sceneBoundingRect().contains(pos)
            and self.df is not None
            and not self.df.empty
        ):
            # 마우스 좌표를 차트 내부 데이터 좌표로 변환
            mouse_point = self.plotItem.vb.mapSceneToView(pos)
            x_idx = int(round(mouse_point.x()))

            # x 인덱스가 데이터 범위 안에 있는지 확인
            if 0 <= x_idx < len(self.df):
                row = self.df.iloc[x_idx]

                # 데이터 추출
                date_str = (
                    self.date_strings[x_idx]
                    if x_idx < len(self.date_strings)
                    else "N/A"
                )
                close_p = row["close"]

                upper_col = [c for c in self.df.columns if c.startswith("BBU_")]
                lower_col = [c for c in self.df.columns if c.startswith("BBL_")]

                upper_b = row[upper_col[0]] if upper_col else 0
                lower_b = row[lower_col[0]] if lower_col else 0

                # 툴팁에 띄울 HTML 디자인
                html_text = (
                    f"<div style='color: #eeeeee; font-family: sans-serif; font-size: 13px;'>"
                    f"<b>{date_str}</b><br><hr style='border: 1px solid #444;'/>"
                    f"<span style='color: #aaaaaa;'>현재가:</span> <b style='color: #00bfff;'>{close_p:,.0f}원</b><br>"
                    f"<span style='color: #aaaaaa;'>BB상단:</span> <b style='color: #ffff00;'>{upper_b:,.0f}</b><br>"
                    f"<span style='color: #aaaaaa;'>BB하단:</span> <b style='color: #ffff00;'>{lower_b:,.0f}</b>"
                    f"</div>"
                )

                self.tooltip.setHtml(html_text)

                # 마우스 커서 위치에 맞춰서 툴팁과 십자선 이동
                self.tooltip.setPos(mouse_point.x(), mouse_point.y())
                self.vLine.setPos(mouse_point.x())
                self.hLine.setPos(mouse_point.y())

                # 화면에 표시
                self.vLine.show()
                self.hLine.show()
                self.tooltip.show()
        else:
            # 마우스가 차트 밖으로 나가면 숨김
            self.vLine.hide()
            self.hLine.hide()
            self.tooltip.hide()
