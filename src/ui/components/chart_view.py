import pandas as pd
import pyqtgraph as pg
from pyqtgraph import QtCore, QtGui


class CandlestickItem(pg.GraphicsObject):
    def __init__(self, data):
        pg.GraphicsObject.__init__(self)
        self.data = data  # (index, open, close, low, high) 리스트
        self.generatePicture()

    def generatePicture(self):
        self.picture = QtGui.QPicture()
        p = QtGui.QPainter(self.picture)
        p.setPen(pg.mkPen('w'))
        w = 0.6  # 봉 너비
        for t, open, close, low, high in self.data:
            if open > close:
                p.setBrush(pg.mkBrush('b')) # 하락 파란색
            else:
                p.setBrush(pg.mkBrush('r')) # 상승 빨간색
            p.drawLine(QtCore.QPointF(t, low), QtCore.QPointF(t, high))
            p.drawRect(QtCore.QRectF(t - w/2, open, w, close - open))
        p.end()

    def paint(self, p, *args):
        p.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        return QtCore.QRectF(self.picture.boundingRect())

class StockChart(pg.PlotWidget):
    def __init__(self):
        super().__init__()
        self.setBackground('#2b2b2b')
        self.showGrid(x=True, y=True, alpha=0.3)

    def update_chart(self, df):
        self.clear()
        
        # 1. 캔들스틱 추가
        data_list = []
        for i, row in df.iterrows():
            data_list.append((i, row['open'], row['close'], row['low'], row['high']))
        
        candle_item = CandlestickItem(data_list)
        self.addItem(candle_item)

        # 2. 볼린저밴드 추가 (BBU: 상단, BBL: 하단, BBM: 중앙)
        self.plot(df.index, df['BBU_20_2.0'], pen=pg.mkPen('y', width=1, style=QtCore.Qt.PenStyle.DashLine))
        self.plot(df.index, df['BBL_20_2.0'], pen=pg.mkPen('y', width=1, style=QtCore.Qt.PenStyle.DashLine))
        self.plot(df.index, df['BBM_20_2.0'], pen=pg.mkPen('gray', width=0.8))