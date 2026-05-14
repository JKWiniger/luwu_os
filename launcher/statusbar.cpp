#include "statusbar.h"
#include <QFile>
#include <QDateTime>
#include <QResizeEvent>
#include <QPainter>
#include <QFont>
#include <QFontMetrics>

StatusBar::StatusBar(QWidget *parent) : QWidget(parent) {
    // 完全透明，不拦截鼠标/按键事件
    setAttribute(Qt::WA_TransparentForMouseEvents);
    setAttribute(Qt::WA_TranslucentBackground);
    setFixedHeight(26);

    updateStatus();

    timer = new QTimer(this);
    connect(timer, &QTimer::timeout, this, &StatusBar::updateStatus);
    timer->start(10000); // 每 10 秒刷新一次
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

    QFont font = painter.font();
    font.setPixelSize(12);
    font.setBold(true);
    painter.setFont(font);
    painter.setPen(QColor(0x5a, 0x64, 0x99));

    QFontMetrics fm(font);
    QRect textRect = fm.boundingRect(displayText);

    int x = (width() - textRect.width()) / 2;
    int y = (height() + fm.ascent()) / 2; // 基线居中

    painter.drawText(x, y, displayText);
}

void StatusBar::updateStatus() {
    QString timeStr = QDateTime::currentDateTime().toString("HH:mm");
    QString battStr = readBattery();

    if (battStr.isEmpty()) {
        displayText = timeStr;
    } else {
        // 中间点分隔符 U+00B7
        displayText = timeStr + "  \u00b7  " + battStr;
    }
    update(); // 触发重绘
}

QString StatusBar::readBattery() {
    QFile f("/tmp/luwu_battery_level");
    if (f.open(QIODevice::ReadOnly)) {
        bool ok;
        int val = f.readAll().trimmed().toInt(&ok);
        if (ok && val >= 0 && val <= 100) {
            return QString::number(val) + "%";
        }
    }
    return {};
}
