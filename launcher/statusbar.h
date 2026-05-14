#pragma once
#include <QWidget>
#include <QTimer>

// ========================================================================
// StatusBar: 顶部中央时间 + 电量悬浮覆盖层
// 透明背景，配色与桌面主题一致（#8892c9 蓝灰色文字）
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
    QString displayText;
    QTimer *timer = nullptr;

    QString readBattery();
};
