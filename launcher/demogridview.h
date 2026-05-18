#pragma once
#include <QWidget>
#include <QLabel>
#include <QVector>
#include <QRect>

// 设备兼容性表达式（数据驱动，设计先行）
// 语法按逗号 OR：
//   "*"             → 所有机型
//   "@<family>"     → 该家族全部机型（如 "@dog" / "@rider"）
//   "<id>"          → 单一机型（如 "xgomini2sw"）
//   "!<id>"         → 排除某机型（与其他项 AND）
//   组合举例："@dog,!xgolite"  / "@dog,xgorider"  / "xgomini,xgomini2sw"
//
// 机型与家族的查表集中在 devicetable.h 的 DEVICES[]。
// 新增机型只改 DEVICES[]，本文件与 DEMOS[] 不需动。

struct DemoItem {
    const char *name;     // 中文名称
    const char *nameEn;   // 英文名称
    const char *color;    // hex color for placeholder icon
    const char *appPath;  // placeholder, not used yet
    const char *iconFile; // icon image file name
    const char *compat;   // 兼容性表达式，详见上方语法说明
};

class DemoGridView : public QWidget {
    Q_OBJECT
public:
    explicit DemoGridView(QWidget *parent = nullptr);
    ~DemoGridView() override = default;

    void loadImages();
    void moveSelection(int delta);
    int selectedDemoIndex() const { return selectedIdx; }
    QString selectedDemoPath() const;
    void retranslate();  // 重新根据当前语言设置 demo 名称

    // 设置当前设备 ID（"xgomini" / "xgolite" / "xgomini2sw" / "xgorider" 等），
    // 内部根据 DEVICES[] 查家族并重建可见 demo 列表。未知值会保守显示全部。
    void setDeviceType(const QString &devType);

signals:
    void backPressed();
    void demoEntered(const QString &appPath);

protected:
    void resizeEvent(QResizeEvent *) override;
    void keyPressEvent(QKeyEvent *ev) override;

private:
    // 背景 + 四角图标
    QLabel *bgLabel = nullptr;
    QLabel *cornerTL = nullptr;
    QLabel *cornerTR = nullptr;
    QLabel *cornerBL = nullptr;
    QLabel *cornerBR = nullptr;

    // 当前设备 ID（空串 = 未探测，保守显示全部）
    QString currentDeviceId;

    // 当前可见的 demo 项（按 deviceMask 过滤后的结果）
    QVector<DemoItem> demoItems;
    QVector<QLabel*> itemIcons;
    QVector<QLabel*> itemLabels;
    int selectedIdx = 0;
    int currentPage = 0;
    static constexpr int COLUMNS = 3;
    static constexpr int ITEMS_PER_PAGE = 6;  // 每页显示6个

    // 布局参数
    int itemW = 66;
    int itemH = 66;
    int labelH = 12;
    int topOffset = 36;   // 顶部留给角标区域

    void updateCornerPositions();
    void updateItemPositions();
    void updateSelectionStyle();
    // 按 deviceMask 重建可见 demo 列表（含 itemIcons/itemLabels）
    void rebuildVisibleItems();
};
