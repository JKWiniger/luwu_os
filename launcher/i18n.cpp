#include "i18n.h"
#include <QFile>
#include <cstdlib>

namespace luwu {

static QString langIniPath() {
    const char *root = getenv("LUWU_ROOT");
    if (!root) root = "/opt/luwu-os";
    return QString(root) + "/configs/language.ini";
}

QString currentLang() {
    QFile f(langIniPath());
    if (!f.open(QIODevice::ReadOnly | QIODevice::Text)) {
        return QStringLiteral("cn");
    }
    QString v = QString::fromUtf8(f.readAll()).trimmed();
    f.close();
    if (v == QStringLiteral("en")) return v;
    return QStringLiteral("cn");
}

} // namespace luwu
