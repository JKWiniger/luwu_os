#include <QApplication>
#include <QLabel>
#include <QTimer>
#include <QDateTime>
#include <QVBoxLayout>
#include <QProcess>
#include <QProcessEnvironment>
#include <QDebug>
#include <QElapsedTimer>
#include <QKeyEvent>
#include <QResizeEvent>
#include "keyfilter.h"

static constexpr const char *PYQT_SCRIPT = "/home/pi/luwu-os/apps/demo_page/main.py";

// Small helper window that positions a corner label on resize
class MainWindow : public QWidget {
public:
    QLabel *cornerTL = nullptr;
protected:
    void resizeEvent(QResizeEvent *ev) override {
        QWidget::resizeEvent(ev);
        if (cornerTL) {
            cornerTL->adjustSize();
            cornerTL->move(16, 16);
        }
    }
};

int main(int argc, char *argv[]) {
    QApplication app(argc, argv);

    MainWindow window;
    window.setWindowTitle("Luwu OS");
    window.setStyleSheet("background-color: #0a0a1a; color: white;");

    QVBoxLayout *layout = new QVBoxLayout(&window);
    layout->setAlignment(Qt::AlignCenter);

    QLabel *title = new QLabel("Luwu OS");
    title->setStyleSheet("font-size: 24px; font-weight: bold;");
    title->setAlignment(Qt::AlignCenter);

    QLabel *timeLabel = new QLabel();
    timeLabel->setStyleSheet("font-size: 16px;");
    timeLabel->setAlignment(Qt::AlignCenter);

    QLabel *keyLabel = new QLabel("last key: --");
    keyLabel->setStyleSheet("font-size: 12px; color: #5c6a9c;");
    keyLabel->setAlignment(Qt::AlignCenter);

    QLabel *hintLabel = new QLabel("KEY_UP -> PyQt");
    hintLabel->setStyleSheet("font-size: 13px; color: #8892c9;");
    hintLabel->setAlignment(Qt::AlignCenter);

    QLabel *statusLabel = new QLabel("status: idle");
    statusLabel->setStyleSheet("font-size: 12px; color: #5c6a9c;");
    statusLabel->setAlignment(Qt::AlignCenter);

    layout->addWidget(title);
    layout->addWidget(timeLabel);
    layout->addWidget(keyLabel);
    layout->addWidget(hintLabel);
    layout->addWidget(statusLabel);

    // ---- 左上角 Demo 引导文案 ----
    QLabel *demoHint = new QLabel("Demo", &window);
    demoHint->setStyleSheet("color: #18df6b; font-size: 13px; font-weight: bold; background: transparent;");
    window.cornerTL = demoHint;
    demoHint->show();

    auto updateTime = [timeLabel]() {
        timeLabel->setText(QDateTime::currentDateTime().toString("yyyy-MM-dd hh:mm:ss"));
    };
    updateTime();
    QTimer *timer = new QTimer(&window);
    QObject::connect(timer, &QTimer::timeout, updateTime);
    timer->start(1000);

    // --- PyQt child process management ---
    auto *pyProc = new QProcess(&window);
    pyProc->setProcessChannelMode(QProcess::ForwardedChannels);

    QElapsedTimer launchTimer;
    auto launchPyQt = [&, pyProc, statusLabel]() {
        if (pyProc->state() != QProcess::NotRunning) {
            qDebug() << "[luwu-launcher] PyQt already running, ignore";
            return;
        }
        qint64 t_req = QDateTime::currentMSecsSinceEpoch();
        qDebug().noquote() << QString("[luwu-launcher][%1] request -> launch PyQt").arg(t_req);

        // Stop our own UI updates to avoid drawing over the PyQt child on the shared fb
        timer->stop();
        statusLabel->setText("launching PyQt...");
        window.repaint();       // flush the "launching" hint
        window.hide();          // release the fb from our side
        qint64 t_hide = QDateTime::currentMSecsSinceEpoch();
        qDebug().noquote() << QString("[luwu-launcher][%1] ui paused +%2ms").arg(t_hide).arg(t_hide - t_req);

        QProcessEnvironment env = QProcessEnvironment::systemEnvironment();
        env.insert("QT_QPA_PLATFORM", "linuxfb:fb=/dev/fb-spi");
        env.insert("QT_QPA_FONTDIR", "/usr/share/fonts");
        env.insert("PYTHONUNBUFFERED", "1");
        pyProc->setProcessEnvironment(env);
        pyProc->setProgram("python3");
        pyProc->setArguments({PYQT_SCRIPT});
        launchTimer.restart();
        pyProc->start();
        qint64 t_start = QDateTime::currentMSecsSinceEpoch();
        qDebug().noquote() << QString("[luwu-launcher][%1] QProcess::start() returned +%2ms since request").arg(t_start).arg(t_start - t_req);
    };

    QObject::connect(pyProc, &QProcess::started, [statusLabel, &launchTimer]() {
        qint64 ms = launchTimer.elapsed();
        qDebug().noquote() << QString("[luwu-launcher][%1] PyQt QProcess 'started' signal after %2ms (fork+exec)")
                                  .arg(QDateTime::currentMSecsSinceEpoch()).arg(ms);
        statusLabel->setText(QString("PyQt fork+exec in %1 ms").arg(ms));
    });
    QObject::connect(pyProc, QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
        [&, statusLabel](int code, QProcess::ExitStatus st) {
            qint64 total = launchTimer.elapsed();
            qDebug().noquote() << QString("[luwu-launcher][%1] PyQt finished code=%2 status=%3 total=%4ms")
                                      .arg(QDateTime::currentMSecsSinceEpoch()).arg(code).arg(int(st)).arg(total);
            // Resume our own UI
            window.showFullScreen();
            timer->start(1000);
            statusLabel->setText(QString("PyQt exited code=%1 (ran %2ms)").arg(code).arg(total));
            window.repaint();
        });

    // --- Keyboard event handler (gpio-keys kernel driver → QKeyEvent) ---
    auto *keyFilter = new KeyFilter(&window);
    keyFilter->onKey = [&, keyLabel, statusLabel, launchPyQt](QKeyEvent *ke) {
        const char *name = "?";
        switch (ke->key()) {
            case Qt::Key_Up:    name = "KEY_UP";    launchPyQt(); break;
            case Qt::Key_Down:  name = "KEY_DOWN";   break;
            case Qt::Key_Left:  name = "KEY_LEFT";   break;
            case Qt::Key_Right: name = "KEY_RIGHT";  break;
        }
        qDebug().noquote() << QString("[luwu-launcher][%1] key: %2")
                                  .arg(QDateTime::currentMSecsSinceEpoch()).arg(name);
        keyLabel->setText(QString("last key: %1").arg(name));
        statusLabel->setText(QString("key: %1").arg(name));
    };
    window.installEventFilter(keyFilter);
    
    window.showFullScreen();
    int rc = app.exec();
    if (pyProc->state() != QProcess::NotRunning) {
        pyProc->terminate();
        pyProc->waitForFinished(1000);
    }
    return rc;
}
