from bisect import bisect_left, bisect_right

import pandas as pd
import pyqtgraph as pg
from PyQt6 import QtCore


class DateAxis(pg.DateAxisItem):
    def tickStrings(self, values, scale, spacing):
        labels = super().tickStrings(values, scale, spacing)
        return [label.replace("\n", " ") for label in labels]


# Y축 가격 표시를 위한 커스텀 축 클래스
class PriceAxis(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        return [f"{int(value):,}" for value in values if not pd.isna(value)]


class StockChart(pg.PlotWidget):
    visibleRangeChanged = QtCore.pyqtSignal(object, object)

    def __init__(self):
        price_axis = PriceAxis(orientation="left")
        date_axis = DateAxis(orientation="bottom")
        super().__init__(axisItems={"left": price_axis, "bottom": date_axis})

        self.setBackground("#1e1e1e")
        self.showGrid(x=True, y=True, alpha=0.3)
        self.currency = "원"
        self.setLabel("left", "가격", units=self.currency)
        self.setLabel("bottom", "시간/날짜")

        self.df = None
        self.date_strings = []
        self._x_values = []
        self._updating_visible_range = False

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

        self._range_timer = QtCore.QTimer(self)
        self._range_timer.setSingleShot(True)
        self._range_timer.timeout.connect(self._refresh_visible_range)
        self.plotItem.vb.sigXRangeChanged.connect(self._on_x_range_changed)

    def set_currency(self, currency: str):
        self.currency = currency
        self.setLabel("left", "가격", units=currency)

    def _format_price(self, value):
        if self.currency == "USD":
            return f"{value:,.2f} USD"
        return f"{int(value):,}원"

    def update_chart(self, df):
        self.df = df
        self._x_values = self._build_x_values(df)
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

        # 종가 선 그래프
        self.plot(self._x_values, df["close"], pen=pg.mkPen("#00bfff", width=2), name="종가")

        # 볼린저밴드 처리 (pandas_ta가 만들어준 컬럼명을 동적으로 찾음)
        upper_col = [c for c in df.columns if c.startswith("BBU_")]
        lower_col = [c for c in df.columns if c.startswith("BBL_")]
        mid_col = [c for c in df.columns if c.startswith("BBM_")]

        if upper_col and lower_col:
            self.plot(
                self._x_values,
                df[upper_col[0]],
                pen=pg.mkPen("y", width=1, style=QtCore.Qt.PenStyle.DashLine),
            )
            self.plot(
                self._x_values,
                df[lower_col[0]],
                pen=pg.mkPen("y", width=1, style=QtCore.Qt.PenStyle.DashLine),
            )
            if mid_col:
                self.plot(
                    self._x_values,
                    df[mid_col[0]],
                    pen=pg.mkPen(color=(100, 100, 100), width=0.8),
                )

        if len(df) == 1:
            self.setXRange(self._x_values[0] - 86400, self._x_values[0] + 86400, padding=0)
        else:
            self.setXRange(self._x_values[0], self._x_values[-1], padding=0.02)
        self._refresh_visible_range()

    def _build_x_values(self, df) -> list[float]:
        if "datetime" in df.columns:
            dt = pd.to_datetime(df["datetime"], errors="coerce")
        elif "time" in df.columns:
            dt = pd.to_datetime(
                df["date"].astype(str) + df["time"].astype(str).str.zfill(6),
                format="%Y%m%d%H%M%S",
                errors="coerce",
            )
        else:
            dt = pd.to_datetime(df["date"].astype(str), errors="coerce")

        dt = dt.ffill().bfill()
        return [ts.timestamp() for ts in dt]

    def _on_x_range_changed(self, *args):
        if self._updating_visible_range:
            return
        self._range_timer.start(80)

    def _visible_index_range(self) -> tuple[int, int] | None:
        if self.df is None or self.df.empty:
            return None

        left, right = self.plotItem.vb.viewRange()[0]
        start = bisect_left(self._x_values, left)
        end = bisect_right(self._x_values, right) - 1
        if end < start:
            return None
        start = max(0, start)
        end = min(len(self.df) - 1, end)
        return start, end

    def _refresh_visible_range(self):
        left, right = self.plotItem.vb.viewRange()[0]
        self.visibleRangeChanged.emit(
            pd.to_datetime(left, unit="s").to_pydatetime(),
            pd.to_datetime(right, unit="s").to_pydatetime(),
        )

        bounds = self._visible_index_range()
        if bounds is None:
            return

        start, end = bounds
        self._update_visible_y_range(start, end)

    def _update_visible_ticks(self, start: int, end: int):
        if not self.date_strings:
            return

        visible_count = end - start + 1
        max_ticks = 6
        step = max(1, visible_count // max_ticks)
        indices = list(range(start, end + 1, step))
        if indices[-1] != end:
            indices.append(end)

        ticks = [(idx, self.date_strings[idx]) for idx in indices if idx < len(self.date_strings)]
        self.getAxis("bottom").setTicks([ticks])

    def _update_visible_y_range(self, start: int, end: int):
        if self.df is None or self.df.empty:
            return

        band_cols = [
            c for c in self.df.columns
            if c.startswith("BBU_") or c.startswith("BBL_") or c.startswith("BBM_")
        ]
        y_cols = [c for c in ["close", *band_cols] if c in self.df.columns]
        if not y_cols:
            return

        values = (
            self.df.iloc[start:end + 1][y_cols]
            .apply(pd.to_numeric, errors="coerce")
            .to_numpy()
            .ravel()
        )
        values = values[pd.notna(values)]
        if len(values) == 0:
            return

        y_min = float(values.min())
        y_max = float(values.max())
        if y_min == y_max:
            padding = max(abs(y_min) * 0.01, 1)
        else:
            padding = (y_max - y_min) * 0.08

        self._updating_visible_range = True
        try:
            self.setYRange(y_min - padding, y_max + padding, padding=0)
        finally:
            self._updating_visible_range = False

    def mouse_moved(self, evt):
        pos = evt[0]  # 마우스의 화면 좌표
        # 마우스가 차트 영역 안에 있고, 데이터가 로드된 상태일 때만 동작
        if (
            self.sceneBoundingRect().contains(pos)
            and self.df is not None
            and not self.df.empty
            and self._x_values
        ):
            # 마우스 좌표를 차트 내부 데이터 좌표로 변환
            mouse_point = self.plotItem.vb.mapSceneToView(pos)
            mouse_x = mouse_point.x()
            x_idx = min(
                range(len(self._x_values)),
                key=lambda idx: abs(self._x_values[idx] - mouse_x),
            )

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
                    f"<span style='color: #aaaaaa;'>현재가:</span> <b style='color: #00bfff;'>{self._format_price(close_p)}</b><br>"
                    f"<span style='color: #aaaaaa;'>BB상단:</span> <b style='color: #ffff00;'>{upper_b:,.0f}</b><br>"
                    f"<span style='color: #aaaaaa;'>BB하단:</span> <b style='color: #ffff00;'>{lower_b:,.0f}</b>"
                    f"</div>"
                )

                self.tooltip.setHtml(html_text)

                # 마우스 커서 위치에 맞춰서 툴팁과 십자선 이동
                self.tooltip.setPos(self._x_values[x_idx], mouse_point.y())
                self.vLine.setPos(self._x_values[x_idx])
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
