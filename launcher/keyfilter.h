#pragma once
#include <QObject>
#include <QKeyEvent>
#include <functional>

// Keyboard event filter: bridges gpio-keys kernel driver → Qt key events
class KeyFilter : public QObject {
public:
    explicit KeyFilter(QObject *parent = nullptr) : QObject(parent) {}
    std::function<void(QKeyEvent*)> onKey;

protected:
    bool eventFilter(QObject *obj, QEvent *ev) override {
        if (ev->type() == QEvent::KeyPress) {
            auto *ke = static_cast<QKeyEvent*>(ev);
            if (onKey) onKey(ke);
            return true;
        }
        return QObject::eventFilter(obj, ev);
    }
};
