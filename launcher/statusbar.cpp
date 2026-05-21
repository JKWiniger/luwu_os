#include "statusbar.h"
#include <QFile>
#include <QDir>
#include <QFileInfo>
#include <QDateTime>
#include <QResizeEvent>
#include <QPainter>
#include <QPen>
#include <QFont>
#include <QFontMetrics>
#include <QRectF>

StatusBar::StatusBar(QWidget *parent) : QWidget(parent) {
    // 完全透明，不拦截鼠标/按键事件
    setAttribute(Qt::WA_TransparentForMouseEvents);
    setAttribute(Qt::WA_TranslucentBackground);
    // linuxfb 上 WA_TranslucentBackground 不能阻止 Qt 用调色板默认色预填充背景，
    // WA_NoSystemBackground 明确告知 Qt：不要在 paintEvent 前填充任何系统背景
    setAttribute(Qt::WA_NoSystemBackground);
    setFixedHeight(26);

    updateStatus();

    timer = new QTimer(this);
    connect(timer, &QTimer::timeout, this, &StatusBar::updateStatus);
    timer->start(5000); // 每 5 秒刷新一次（时间/电量/WiFi）
}

void StatusBar::resizeEvent(QResizeEvent *ev) {
    QWidget::resizeEvent(ev);
    // 确保自身宽度始终和父部件一致（防止 singleShot 时父部件尺寸未就绪）
    if (parentWidget() && parentWidget()->width() != width()) {
        setGeometry(0, 0, parentWidget()->width(), 26);
    }
}

void StatusBar::paintEvent(QPaintEvent *) {
    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing, true);
    painter.setRenderHint(QPainter::TextAntialiasing, true);

    const QColor themeColor(0x5a, 0x64, 0x99);

    // 1) 中央时间
    QString timeStr = QDateTime::currentDateTime().toString("HH:mm");
    QFont tfont = painter.font();
    tfont.setPixelSize(12);
    tfont.setWeight(QFont::Medium);
    painter.setFont(tfont);
    painter.setPen(themeColor);
    QFontMetrics tfm(tfont);
    int tw = tfm.horizontalAdvance(timeStr);
    int tx = (width() - tw) / 2;
    int ty = (height() + tfm.ascent()) / 2 - 1;
    painter.drawText(tx, ty, timeStr);

    // 2) 左侧图标区：避开左上角图标（0~28px），从 x=40 开始
    //    顺序：WiFi 在前，电池在后
    const int leftStart = 40;       // 距左边 40px，与左上角图标隔开 12px
    const int wifiSize  = 14;
    const int gapBetween = 8;
    const int battCapW  = 2;
    const int battBodyW = 28;
    const int battBodyH = 13;

    int wifiX = leftStart;
    int wifiY = (height() - wifiSize) / 2 - 2; // 上移 2px：信号弧从底部圆点扣出，视觉重心偏下，需补偿
    drawWifiIcon(painter, wifiX, wifiY, wifiSize, themeColor, wifiConnected);

    int battBodyX = wifiX + wifiSize + gapBetween;
    int battBodyY = (height() - battBodyH) / 2;
    if (batteryLevel >= 0) {
        drawBatteryIcon(painter, battBodyX, battBodyY,
                        battBodyW, battBodyH, batteryLevel, themeColor);
    }
    (void)battCapW; // 仅用于说明实际占宽，表达上使用
}

void StatusBar::updateStatus() {
    batteryLevel   = readBattery();
    wifiConnected  = readWifiConnected();
    update(); // 触发重绘
}

int StatusBar::readBattery() {
    QFile f("/tmp/luwu_battery_level");
    if (f.open(QIODevice::ReadOnly)) {
        bool ok;
        int val = f.readAll().trimmed().toInt(&ok);
        if (ok && val >= 0 && val <= 100) return val;
    }
    return -1;
}

bool StatusBar::readWifiConnected() {
    // 遍历 /sys/class/net 找出无线接口（存在 wireless 目录），任一 carrier=1 即视为已连接
    QDir netDir("/sys/class/net");
    const QStringList ifaces = netDir.entryList(QDir::Dirs | QDir::NoDotAndDotDot);
    for (const QString &iface : ifaces) {
        QFileInfo wirelessInfo("/sys/class/net/" + iface + "/wireless");
        if (!wirelessInfo.exists()) continue;
        QFile carrier("/sys/class/net/" + iface + "/carrier");
        if (carrier.open(QIODevice::ReadOnly)) {
            QString val = QString::fromLatin1(carrier.readAll()).trimmed();
            if (val == "1") return true;
        }
    }
    return false;
}

void StatusBar::drawBatteryIcon(QPainter &p, int bodyX, int bodyY,
                                int bodyW, int bodyH, int level,
                                const QColor &themeColor)
{
    p.save();

    // 电池外框
    QPen outline(themeColor);
    outline.setWidthF(1.2);
    p.setPen(outline);
    p.setBrush(Qt::NoBrush);
    QRectF body(bodyX + 0.5, bodyY + 0.5, bodyW - 1, bodyH - 1);
    p.drawRoundedRect(body, 2.0, 2.0);

    // 电池正极头
    p.setPen(Qt::NoPen);
    p.setBrush(themeColor);
    int capH = 6;
    int capY = bodyY + (bodyH - capH) / 2;
    p.drawRect(QRectF(bodyX + bodyW, capY, 2, capH));

    // 电量填充（按等级配色）
    QColor fillColor;
    if (level >= 50)      fillColor = QColor(0x6e, 0xa8, 0xd5); // 蓝（足）
    else if (level >= 20) fillColor = QColor(0xd9, 0xa0, 0x5b); // 黄（中）
    else                  fillColor = QColor(0xc9, 0x5a, 0x5a); // 红（低）

    int innerPad = 2;
    int innerW = bodyW - innerPad * 2;
    int innerH = bodyH - innerPad * 2;
    int fillW = innerW * level / 100;
    if (fillW > 0) {
        QRectF fillRect(bodyX + innerPad, bodyY + innerPad, fillW, innerH);
        p.setBrush(fillColor);
        p.drawRoundedRect(fillRect, 1.0, 1.0);
    }

    // 数字（居中显示在电池内）
    QFont nfont = p.font();
    nfont.setPixelSize(9);
    nfont.setWeight(QFont::Bold);
    p.setFont(nfont);
    p.setPen(themeColor);
    QFontMetrics nfm(nfont);
    QString numStr = QString::number(level);
    int nw = nfm.horizontalAdvance(numStr);
    int nx = bodyX + (bodyW - nw) / 2;
    int ny = bodyY + (bodyH + nfm.ascent()) / 2 - 1;
    p.drawText(nx, ny, numStr);

    p.restore();
}

void StatusBar::drawWifiIcon(QPainter &p, int x, int y, int size,
                             const QColor &themeColor, bool connected)
{
    p.save();

    QColor mainColor = connected ? themeColor : QColor(0xa8, 0xae, 0xc4);

    // 信号弧的圆心位于图标底部中心
    qreal cx = x + size / 2.0;
    qreal cy = y + size - 2.0;

    // 中心圆点
    p.setPen(Qt::NoPen);
    p.setBrush(mainColor);
    p.drawEllipse(QPointF(cx, cy), 1.3, 1.3);

    // 三层同心弧（从内到外）
    QPen arcPen(mainColor);
    arcPen.setWidthF(1.4);
    arcPen.setCapStyle(Qt::RoundCap);
    p.setPen(arcPen);
    p.setBrush(Qt::NoBrush);
    for (int i = 1; i <= 3; ++i) {
        qreal r = i * 3.0;
        QRectF rect(cx - r, cy - r, 2 * r, 2 * r);
        // Qt 角度：0° 为 3 点钟方向，逆时针。45°→135° 即顶部 90° 弧
        p.drawArc(rect, 45 * 16, 90 * 16);
    }

    // 未连接：右下角叠一个红色 "x" 标记
    if (!connected) {
        QPen xPen(QColor(0xc9, 0x5a, 0x5a));
        xPen.setWidthF(1.4);
        xPen.setCapStyle(Qt::RoundCap);
        p.setPen(xPen);
        qreal x0 = cx + 2.0;
        qreal y0 = cy - 6.0;
        qreal sz = 4.5;
        p.drawLine(QPointF(x0, y0), QPointF(x0 + sz, y0 + sz));
        p.drawLine(QPointF(x0 + sz, y0), QPointF(x0, y0 + sz));
    }

    p.restore();
}
