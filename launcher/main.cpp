#include <QApplication>
#include <QStackedWidget>
#include <QLabel>
#include <QTimer>
#include <QDateTime>
#include <QProcess>
#include <QProcessEnvironment>
#include <QDebug>
#include <QElapsedTimer>
#include <QKeyEvent>
#include <QFile>
#include <QPixmap>
#include <QPainter>
#include <sys/stat.h>
#include <unistd.h>
#include "keyfilter.h"
#include "galleryview.h"
#include "demogridview.h"

// ========================================================================
// 配置常量
// ========================================================================
static constexpr const char *PRELOAD_SCRIPT = "/home/pi/luwu-os/apps/demo_page/preload_app.py";
static constexpr const char *FIFO_PATH = "/tmp/luwu_preload.fifo";

// ========================================================================
// Main
// ========================================================================
int main(int argc, char *argv[]) {
    QApplication app(argc, argv);

    // --- 页面栈 ---
    QStackedWidget stack;
    stack.setWindowTitle("Luwu OS");

    GalleryView *gallery = new GalleryView(&stack);
    DemoGridView *demoGrid = new DemoGridView(&stack);

    stack.addWidget(gallery);   // index 0: 主菜单
    stack.addWidget(demoGrid);  // index 1: demo 网格页
    stack.setCurrentIndex(0);

    // --- 预加载子进程管理 ---
    auto *preloadProc = new QProcess(&stack);
    preloadProc->setProcessChannelMode(QProcess::ForwardedChannels);

    QElapsedTimer launchTimer;

    auto startPreload = [&]() {
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
        qDebug().noquote() << QString("[luwu-launcher][%1] preload started").arg(t);
    };

    QObject::connect(preloadProc, QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
        [&](int code, QProcess::ExitStatus st) {
            qint64 total = launchTimer.elapsed();
            qDebug().noquote() << QString("[luwu-launcher][%1] PySide finished code=%2 status=%3 total=%4ms")
                                      .arg(QDateTime::currentMSecsSinceEpoch()).arg(code).arg(int(st)).arg(total);
            stack.showFullScreen();
            // 切回主菜单
            stack.setCurrentIndex(0);
            gallery->setFocus();
            QTimer::singleShot(300, &stack, startPreload);
        });

    auto launchApp = [&](const QString &script) {
        if (preloadProc->state() == QProcess::NotRunning) {
            qDebug() << "[luwu-launcher] preload not running, starting now...";
            startPreload();
            return;
        }
        qint64 t_req = QDateTime::currentMSecsSinceEpoch();
        qDebug().noquote() << QString("[luwu-launcher][%1] request -> trigger (%2)")
                                  .arg(t_req).arg(script);

        stack.repaint();
        launchTimer.restart();

        QFile fifo(FIFO_PATH);
        if (fifo.open(QIODevice::WriteOnly)) {
            QByteArray line = script.toUtf8() + '\n';
            fifo.write(line);
            fifo.close();
            qint64 t_done = QDateTime::currentMSecsSinceEpoch();
            qDebug().noquote() << QString("[luwu-launcher][%1] FIFO written +%2ms")
                                      .arg(t_done).arg(t_done - t_req);
        } else {
            qWarning() << "[luwu-launcher] failed to open FIFO for writing";
            stack.showFullScreen();
        }
    };

    startPreload();

    // --- 按键处理（keyfilter 全局拦截，按当前页面分发） ---
    auto *keyFilter = new KeyFilter(&stack);
    keyFilter->onKey = [&](QKeyEvent *ke) {
        const char *name = "?";
        int currentPage = stack.currentIndex();

        if (currentPage == 0) {
            // ========== GalleryView (主菜单) ==========
            switch (ke->key()) {
            case Qt::Key_Left:
                name = "KEY_LEFT(A)->LEFT";
                if (!gallery->isAnimating()) { gallery->moveSelection(-1); }
                break;
            case Qt::Key_Right:
                name = "KEY_RIGHT(B)->RIGHT";
                if (!gallery->isAnimating()) { gallery->moveSelection(1); }
                break;
            case Qt::Key_Return: {
                name = "KEY_ENTER(D)->ENTER";
                if (!gallery->isAnimating()) {
                    int idx = gallery->selectedIndex();
                    if (idx == 3) {
                        // Demo 卡片 → 切换到 demo 网格页
                        qDebug() << "[luwu-launcher] opening demo grid...";
                        demoGrid->resize(stack.size());
                        stack.setCurrentIndex(1);
                        demoGrid->setFocus();
                    } else {
                        QString app = gallery->selectedAppPath();
                        if (QFile::exists(app)) {
                            launchApp(QString("apps/") + CARDS[idx].appPath);
                        } else {
                            qDebug() << "[luwu-launcher] app not found:" << app;
                        }
                    }
                }
                break;
            }
            case Qt::Key_Back:
                name = "KEY_BACK(C)->BACK";
                break;
            }
        } else {
            // ========== DemoGridView (demo 网格页) ==========
            switch (ke->key()) {
            case Qt::Key_Left:
                name = "KEY_LEFT(A)->LEFT";
                demoGrid->moveSelection(-1);
                break;
            case Qt::Key_Right:
                name = "KEY_RIGHT(B)->RIGHT";
                demoGrid->moveSelection(1);
                break;
            case Qt::Key_Return:
                name = "KEY_ENTER(D)->ENTER";
                {
                    QString demoPath = demoGrid->selectedDemoPath();
                    if (!demoPath.isEmpty()) {
                        launchApp(demoPath);
                    } else {
                        qDebug() << "[luwu-launcher] demo placeholder, no app to launch";
                    }
                }
                break;
            case Qt::Key_Back:
                name = "KEY_BACK(C)->BACK";
                stack.setCurrentIndex(0);
                gallery->setFocus();
                break;
            }
        }

        qDebug().noquote() << QString("[luwu-launcher][%1] key: %2 page=%3 idx=%4")
                                  .arg(QDateTime::currentMSecsSinceEpoch())
                                  .arg(name)
                                  .arg(currentPage)
                                  .arg(currentPage == 0 ? gallery->selectedIndex()
                                                        : demoGrid->selectedDemoIndex());
    };
    qApp->installEventFilter(keyFilter);

    stack.showFullScreen();
    gallery->setFocus();

    int rc = app.exec();

    if (preloadProc->state() != QProcess::NotRunning) {
        preloadProc->terminate();
        preloadProc->waitForFinished(1000);
    }
    unlink(FIFO_PATH);
    return rc;
}
