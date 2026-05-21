#pragma once
#include <QWidget>
#include <QTimer>
#include <QColor>

class QPainter;

// ========================================================================
// StatusBar: 顶部状态栏
//   - 中央：当前时间 HH:mm
//   - 右侧：WiFi 图标（已连/未连） + 电池图标（数字显示在电池内部）
// 透明背景，配色与桌面主题一致（#5a6499 蓝灰色）
// ========================================================================
class StatusBar : public QWidget {
    Q_OBJECT
public:
    explicit StatusBar(QWidget *parent = nullptr);

protected:
    void paintEvent(QPaintEvent *ev) override;
    void resizeEvent(QResizeEvent *ev) override;

private slots:
    void updateStatus();

private:
    QTimer *timer = nullptr;
    int batteryLevel = -1;       // -1 = 未知, 0~100
    bool wifiConnected = false;

    int  readBattery();
    bool readWifiConnected();

    // 在指定区域内绘制电池图标，数字居中显示在内部
    void drawBatteryIcon(QPainter &p, int bodyX, int bodyY,
                         int bodyW, int bodyH, int level,
                         const QColor &themeColor);
    // 绘制 WiFi 图标（已连/未连两态）
    void drawWifiIcon(QPainter &p, int x, int y, int size,
                      const QColor &themeColor, bool connected);
};
