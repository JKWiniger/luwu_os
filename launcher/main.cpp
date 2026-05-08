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
#include <QFile>
#include <sys/stat.h>
#include <unistd.h>
#include "keyfilter.h"

static constexpr const char *PRELOAD_SCRIPT = "/home/pi/luwu-os/apps/demo_page/preload_app.py";
static constexpr const char *FIFO_PATH = "/tmp/luwu_preload.fifo";

// App registry: key → relative path (from /home/pi/luwu-os/)
static constexpr const char *APP_DEMO  = "apps/demo_page/main.py";
// Future apps:
// static constexpr const char *APP_SETTINGS = "apps/settings/main.py";
// static constexpr const char *APP_MUSIC    = "apps/music/main.py";

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

    QLabel *hintLabel = new QLabel("UP=Demo");
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

    // --- Preload child process management (FIFO-based) ---
    // Launcher spawns a python process that imports PySide6 early, then blocks on a FIFO.
    // User keypress writes to the FIFO → app starts instantly (no cold import).
    auto *preloadProc = new QProcess(&window);
    preloadProc->setProcessChannelMode(QProcess::ForwardedChannels);

    QElapsedTimer launchTimer;

    auto startPreload = [&]() {
        // Recreate FIFO for the new cycle
        unlink(FIFO_PATH);
        if (mkfifo(FIFO_PATH, 0666) != 0) {
            qWarning() << "[luwu-launcher] mkfifo failed";
        }

        QProcessEnvironment env = QProcessEnvironment::systemEnvironment();
        env.insert("QT_QPA_PLATFORM", "linuxfb:fb=/dev/fb-spi");
        env.insert("QT_QPA_FONTDIR", "/usr/share/fonts");
        env.insert("PYTHONUNBUFFERED", "1");
        preloadProc->setProcessEnvironment(env);
        preloadProc->setProgram("python3");
        preloadProc->setArguments({PRELOAD_SCRIPT});
        preloadProc->start();

        qint64 t = QDateTime::currentMSecsSinceEpoch();
        qDebug().noquote() << QString("[luwu-launcher][%1] preload process started").arg(t);
        statusLabel->setText("preloading...");
    };

    // When the preload/app process finishes, restore launcher UI and respawn preload
    QObject::connect(preloadProc, QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
        [&](int code, QProcess::ExitStatus st) {
            qint64 total = launchTimer.elapsed();
            qDebug().noquote() << QString("[luwu-launcher][%1] PySide finished code=%2 status=%3 total=%4ms")
                                      .arg(QDateTime::currentMSecsSinceEpoch()).arg(code).arg(int(st)).arg(total);
            // Resume launcher UI
            window.showFullScreen();
            timer->start(1000);
            statusLabel->setText(QString("PySide exited code=%1 (ran %2ms)").arg(code).arg(total));
            window.repaint();
            // Start next preload after a short delay (let fb settle)
            QTimer::singleShot(300, &window, startPreload);
        });

    // Trigger the waiting preload process via FIFO
    auto launchApp = [&](const QString &script) {
        if (preloadProc->state() == QProcess::NotRunning) {
            qDebug() << "[luwu-launcher] preload not running, starting now...";
            startPreload();
            return;
        }
        qint64 t_req = QDateTime::currentMSecsSinceEpoch();
        qDebug().noquote() << QString("[luwu-launcher][%1] request -> trigger preload (%2)").arg(t_req).arg(script);

        // Stop launcher UI timer (keep content on screen so no black flash)
        timer->stop();
        statusLabel->setText("launching " + script.section('/', -1));
        window.repaint();
        qint64 t_ready = QDateTime::currentMSecsSinceEpoch();
        qDebug().noquote() << QString("[luwu-launcher][%1] ui frozen +%2ms").arg(t_ready).arg(t_ready - t_req);

        // Write target script path to FIFO to unblock the python process
        launchTimer.restart();
        QFile fifo(FIFO_PATH);
        if (fifo.open(QIODevice::WriteOnly)) {
            QByteArray line = script.toUtf8() + '\n';
            fifo.write(line);
            fifo.close();
            qint64 t_done = QDateTime::currentMSecsSinceEpoch();
            qDebug().noquote() << QString("[luwu-launcher][%1] FIFO written +%2ms").arg(t_done).arg(t_done - t_req);
        } else {
            qWarning() << "[luwu-launcher] failed to open FIFO for writing";
            window.showFullScreen();
            timer->start(1000);
        }
    };

    // Start the first preload immediately (imports happen while user sees launcher)
    startPreload();

    // --- Keyboard event handler (gpio-keys kernel driver → QKeyEvent) ---
    auto *keyFilter = new KeyFilter(&window);
    keyFilter->onKey = [&, keyLabel, statusLabel, launchApp](QKeyEvent *ke) {
        const char *name = "?";
        switch (ke->key()) {
            case Qt::Key_Up:    name = "KEY_UP";    launchApp(APP_DEMO); break;
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
    if (preloadProc->state() != QProcess::NotRunning) {
        preloadProc->terminate();
        preloadProc->waitForFinished(1000);
    }
    unlink(FIFO_PATH);
    return rc;
}
