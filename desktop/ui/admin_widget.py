"""Admin screen: 사용자 관리 + 데이터 관리 (visible to admins only).

Everything is enforced again on the server (/api/hv/admin/*); this screen
only offers the actions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QGuiApplication
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from desktop.core import api_client
from desktop.ui import msgbox, theme


def _fmt_dt(v) -> str:
    return v.strftime("%Y-%m-%d %H:%M") if isinstance(v, datetime) else "-"


def _fmt_bytes(n: int | None) -> str:
    if not n:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024
    return str(n)


def _make_table(headers: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setShowGrid(False)
    t.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(44)
    h = t.horizontalHeader()
    h.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    h.setHighlightSections(False)
    for i in range(len(headers)):
        h.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
    h.setStretchLastSection(True)
    return t


def _item(text: str, data=None, color: str | None = None, bold: bool = False) -> QTableWidgetItem:
    it = QTableWidgetItem(text)
    if data is not None:
        it.setData(Qt.ItemDataRole.UserRole, data)
    if color:
        it.setForeground(QColor(color))
    if bold:
        it.setFont(theme.font(10, QFont.Weight.DemiBold))
    return it


def _btn(text: str, variant: str = "secondary", icon: str | None = None) -> QPushButton:
    b = QPushButton(text)
    if variant:
        theme.set_variant(b, variant)
    if icon:
        b.setIcon(theme.icon(icon, "#FFFFFF" if not variant else theme.TEXT_2, 16))
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


def _run(parent: QWidget, title: str, fn: Callable, *args, **kwargs):
    """Call the API; show the server's message on failure. Returns (ok, result)."""
    try:
        return True, fn(*args, **kwargs)
    except api_client.ApiError as e:
        msgbox.warning(parent, title, e.message)
        return False, None


# ── dialogs ─────────────────────────────────────────────────────────


class TempPasswordDialog(QDialog):
    """Shows a new temporary password once, with a copy button."""

    def __init__(self, username: str, name: str, password: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("임시 비밀번호")
        self.setFixedWidth(420)
        ly = QVBoxLayout(self)
        ly.setContentsMargins(28, 24, 28, 22)
        ly.setSpacing(8)
        ly.addWidget(theme.label("임시 비밀번호", "title"))
        info = theme.label(
            f"{name} ({username}) 선생님께 전달해 주세요.\n"
            "이 창을 닫으면 다시 볼 수 없습니다. 로그인 후 🔑 버튼으로 바꾸도록 안내하세요.",
            "subtitle",
        )
        info.setWordWrap(True)
        ly.addWidget(info)
        ly.addSpacing(8)

        box = QFrame()
        box.setObjectName("pwBox")
        box.setStyleSheet(
            f"QFrame#pwBox {{ background: {theme.PRIMARY_SOFT}; border: 1px solid #D6E0FF; border-radius: 10px; }}"
        )
        b_ly = QHBoxLayout(box)
        b_ly.setContentsMargins(16, 12, 12, 12)
        pw = QLabel(password)
        pw.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        pw.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {theme.PRIMARY_PRESSED}; letter-spacing: 1px;")
        b_ly.addWidget(pw, 1)
        copy = _btn("  복사", "secondary", "copy")
        copy.clicked.connect(lambda: (QGuiApplication.clipboard().setText(password), copy.setText("  복사됨")))
        b_ly.addWidget(copy)
        ly.addWidget(box)
        ly.addSpacing(12)

        ok = QPushButton("확인")
        ok.setMinimumWidth(100)
        ok.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(ok)
        ly.addLayout(row)


class AddUserDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("사용자 추가")
        self.setFixedWidth(400)
        self.result_user: dict | None = None
        ly = QVBoxLayout(self)
        ly.setContentsMargins(28, 24, 28, 22)
        ly.setSpacing(6)
        ly.addWidget(theme.label("사용자 추가", "title"))
        sub = theme.label("임시 비밀번호가 자동으로 만들어집니다.", "subtitle")
        ly.addWidget(sub)
        ly.addSpacing(12)

        ly.addWidget(theme.label("아이디", "field"))
        self._username = QLineEdit()
        self._username.setPlaceholderText("예: d03")
        self._username.setMinimumHeight(38)
        ly.addWidget(self._username)
        ly.addSpacing(6)
        ly.addWidget(theme.label("이름", "field"))
        self._name = QLineEdit()
        self._name.setPlaceholderText("예: 홍길동")
        self._name.setMinimumHeight(38)
        ly.addWidget(self._name)
        ly.addSpacing(6)
        self._admin = QCheckBox("관리자 권한 부여")
        ly.addWidget(self._admin)

        self._error = theme.label("", "error")
        ly.addWidget(self._error)
        ly.addSpacing(8)

        row = QHBoxLayout()
        row.addStretch()
        cancel = _btn("취소")
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        self._ok = QPushButton("추가")
        self._ok.setMinimumWidth(100)
        self._ok.setDefault(True)
        self._ok.clicked.connect(self._submit)
        row.addWidget(self._ok)
        ly.addLayout(row)
        self._username.setFocus()

    def _submit(self) -> None:
        username, name = self._username.text().strip(), self._name.text().strip()
        if not username or not name:
            self._error.setText("아이디와 이름을 입력해 주세요.")
            return
        try:
            self.result_user = api_client.admin_create_user(username, name, self._admin.isChecked())
        except api_client.ApiError as e:
            self._error.setText(e.message)
            return
        self.accept()


# ── pages ───────────────────────────────────────────────────────────


class UsersPage(QWidget):
    changed = pyqtSignal()

    COLS = ["아이디", "이름", "권한", "상태", "케이스", "마지막 로그인", "등록일"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._users: list[dict] = []
        ly = QVBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(12)

        card = theme.card()
        c_ly = QVBoxLayout(card)
        c_ly.setContentsMargins(0, 0, 0, 0)
        c_ly.setSpacing(0)

        bar = QHBoxLayout()
        bar.setContentsMargins(20, 16, 20, 12)
        bar.addWidget(theme.label("사용자", "section"))
        self._count = theme.label("", "caption")
        bar.addSpacing(8)
        bar.addWidget(self._count)
        bar.addStretch()
        add = _btn("  사용자 추가", "", "plus")
        add.clicked.connect(self._add)
        bar.addWidget(add)
        c_ly.addLayout(bar)

        self._table = _make_table(self.COLS)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.itemSelectionChanged.connect(self._update_buttons)
        c_ly.addWidget(self._table, 1)

        actions = QHBoxLayout()
        actions.setContentsMargins(20, 12, 20, 16)
        actions.setSpacing(8)
        self._sel_label = theme.label("사용자를 선택하세요", "caption")
        actions.addWidget(self._sel_label)
        actions.addStretch()
        self._b_rename = _btn("이름 변경")
        self._b_reset = _btn("비밀번호 초기화", icon="key")
        self._b_active = _btn("사용 중지")
        self._b_admin = _btn("관리자 지정")
        self._b_transfer = _btn("케이스 이관")
        self._b_delete = _btn("삭제", "danger-ghost", "trash")
        for b, fn in (
            (self._b_rename, self._rename), (self._b_reset, self._reset),
            (self._b_active, self._toggle_active), (self._b_admin, self._toggle_admin),
            (self._b_transfer, self._transfer), (self._b_delete, self._delete),
        ):
            b.clicked.connect(fn)
            actions.addWidget(b)
        c_ly.addLayout(actions)
        ly.addWidget(card, 1)
        self._update_buttons()

    # data
    def refresh(self) -> None:
        ok, users = _run(self, "사용자 목록", api_client.admin_list_users)
        if not ok:
            return
        self._users = users
        me = (api_client.current_doctor() or {}).get("id")
        self._table.setRowCount(len(users))
        for r, u in enumerate(users):
            mine = u["id"] == me
            self._table.setItem(r, 0, _item(u["username"] + ("  (나)" if mine else ""), u["id"], bold=True))
            self._table.setItem(r, 1, _item(u["name"]))
            self._table.setItem(r, 2, _item("관리자" if u["isAdmin"] else "의사",
                                            color=theme.PRIMARY if u["isAdmin"] else theme.TEXT_2))
            self._table.setItem(r, 3, _item("사용" if u["isActive"] else "중지",
                                            color=theme.SUCCESS if u["isActive"] else theme.DANGER))
            self._table.setItem(r, 4, _item(str(u["caseCount"])))
            self._table.setItem(r, 5, _item(_fmt_dt(u.get("lastLoginAt")), color=theme.TEXT_2))
            self._table.setItem(r, 6, _item(_fmt_dt(u.get("createdAt"))[:10], color=theme.TEXT_2))
        self._count.setText(f"{len(users)}명")
        self._update_buttons()

    def _selected(self) -> dict | None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return None
        uid = self._table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        return next((u for u in self._users if u["id"] == uid), None)

    def _update_buttons(self) -> None:
        u = self._selected()
        me = (api_client.current_doctor() or {}).get("id")
        for b in (self._b_rename, self._b_reset, self._b_active, self._b_admin, self._b_transfer, self._b_delete):
            b.setEnabled(u is not None)
        if not u:
            self._sel_label.setText("사용자를 선택하세요")
            return
        self._sel_label.setText(f"선택: {u['name']} ({u['username']})")
        self._b_active.setText("사용 재개" if not u["isActive"] else "사용 중지")
        self._b_admin.setText("관리자 해제" if u["isAdmin"] else "관리자 지정")
        is_self = u["id"] == me
        self._b_active.setEnabled(not is_self)
        self._b_admin.setEnabled(not is_self)
        self._b_delete.setEnabled(not is_self and u["caseCount"] == 0)
        self._b_transfer.setEnabled(u["caseCount"] > 0)

    # actions
    def _done(self) -> None:
        self.refresh()
        self.changed.emit()

    def _add(self) -> None:
        dlg = AddUserDialog(self)
        if dlg.exec() and dlg.result_user:
            u = dlg.result_user
            TempPasswordDialog(u["username"], u["name"], u["tempPassword"], self).exec()
            self._done()

    def _rename(self) -> None:
        u = self._selected()
        name, ok = QInputDialog.getText(self, "이름 변경", f"{u['username']}의 새 이름:", text=u["name"])
        if ok and name.strip() and name.strip() != u["name"]:
            if _run(self, "이름 변경", api_client.admin_update_user, u["id"], name=name.strip())[0]:
                self._done()

    def _reset(self) -> None:
        u = self._selected()
        if msgbox.question(self, "비밀번호 초기화",
                           f"{u['name']} ({u['username']})의 비밀번호를 새 임시 비밀번호로 바꿀까요?\n"
                           "해당 계정은 모든 PC에서 로그아웃됩니다.") != QMessageBox.StandardButton.Yes:
            return
        ok, pw = _run(self, "비밀번호 초기화", api_client.admin_reset_password, u["id"])
        if ok:
            TempPasswordDialog(u["username"], u["name"], pw, self).exec()
            self._done()

    def _toggle_active(self) -> None:
        u = self._selected()
        stop = u["isActive"]
        msg = (f"{u['name']} ({u['username']}) 계정을 사용 중지할까요?\n로그인할 수 없게 되고, 지금 로그인된 PC에서도 로그아웃됩니다.\n"
               "작성한 케이스는 그대로 남습니다." if stop else f"{u['name']} ({u['username']}) 계정을 다시 사용하게 할까요?")
        if msgbox.question(self, "사용 중지" if stop else "사용 재개", msg) != QMessageBox.StandardButton.Yes:
            return
        if _run(self, "상태 변경", api_client.admin_update_user, u["id"], isActive=not stop)[0]:
            self._done()

    def _toggle_admin(self) -> None:
        u = self._selected()
        grant = not u["isAdmin"]
        msg = (f"{u['name']} 선생님을 관리자로 지정할까요?\n사용자와 전체 데이터를 관리할 수 있게 됩니다."
               if grant else f"{u['name']} 선생님의 관리자 권한을 해제할까요?")
        if msgbox.question(self, "관리자 권한", msg) != QMessageBox.StandardButton.Yes:
            return
        if _run(self, "관리자 권한", api_client.admin_update_user, u["id"], isAdmin=grant)[0]:
            self._done()

    def _transfer(self) -> None:
        u = self._selected()
        targets = [x for x in self._users if x["id"] != u["id"] and x["isActive"]]
        if not targets:
            msgbox.information(self, "케이스 이관", "이관받을 수 있는 다른 사용자가 없습니다.")
            return
        labels = [f"{x['name']} ({x['username']})" for x in targets]
        choice, ok = QInputDialog.getItem(
            self, "케이스 이관",
            f"{u['name']} 선생님의 케이스 {u['caseCount']}건을 누구에게 넘길까요?\n"
            "이관받은 선생님이 작성자가 되어 수정할 수 있게 됩니다.",
            labels, 0, False,
        )
        if not ok:
            return
        to = targets[labels.index(choice)]
        ok, moved = _run(self, "케이스 이관", api_client.admin_transfer_cases, u["id"], to["id"])
        if ok:
            msgbox.information(self, "케이스 이관", f"{moved}건을 {to['name']} 선생님에게 이관했습니다.")
            self._done()

    def _delete(self) -> None:
        u = self._selected()
        if msgbox.question(self, "사용자 삭제",
                           f"{u['name']} ({u['username']}) 계정을 삭제할까요?\n되돌릴 수 없습니다.") != QMessageBox.StandardButton.Yes:
            return
        if _run(self, "사용자 삭제", api_client.admin_delete_user, u["id"])[0]:
            self._done()


class DataPage(QWidget):
    changed = pyqtSignal()

    COLS = ["작성일", "환자명", "등록번호", "생년월일", "작성자", "X-ray", "알림톡"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cases: list[dict] = []
        ly = QVBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(12)

        # server status tiles
        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        self._tiles: dict[str, tuple[QLabel, QLabel]] = {}
        for key, caption in (("cases", "케이스"), ("xray", "X-ray 저장"), ("db", "DB 크기"),
                             ("disk", "서버 디스크 여유"), ("backup", "최근 DB 백업")):
            card = theme.card(shadow=False)
            c_ly = QVBoxLayout(card)
            c_ly.setContentsMargins(16, 12, 16, 12)
            c_ly.setSpacing(2)
            c_ly.addWidget(theme.label(caption, "overline"))
            val = QLabel("-")
            val.setStyleSheet("font-size: 17px; font-weight: 700;")
            c_ly.addWidget(val)
            hint = theme.label("", "caption")
            c_ly.addWidget(hint)
            tiles.addWidget(card, 1)
            self._tiles[key] = (val, hint)
        ly.addLayout(tiles)

        card = theme.card()
        c_ly = QVBoxLayout(card)
        c_ly.setContentsMargins(0, 0, 0, 0)
        c_ly.setSpacing(0)
        bar = QHBoxLayout()
        bar.setContentsMargins(20, 16, 20, 12)
        bar.addWidget(theme.label("전체 케이스", "section"))
        self._count = theme.label("", "caption")
        bar.addSpacing(8)
        bar.addWidget(self._count)
        bar.addStretch()
        self._search = QLineEdit()
        self._search.setPlaceholderText("환자명, 등록번호, 작성자 검색")
        self._search.addAction(theme.icon("search", theme.MUTED, 16), QLineEdit.ActionPosition.LeadingPosition)
        self._search.setClearButtonEnabled(True)
        self._search.setFixedWidth(260)
        self._search.setMinimumHeight(36)
        self._search.textChanged.connect(self._fill)
        bar.addWidget(self._search)
        export = _btn("  엑셀(CSV) 내보내기", "secondary", "save")
        export.clicked.connect(self._export)
        bar.addWidget(export)
        c_ly.addLayout(bar)

        self._table = _make_table(self.COLS)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.itemSelectionChanged.connect(self._update_buttons)
        c_ly.addWidget(self._table, 1)

        actions = QHBoxLayout()
        actions.setContentsMargins(20, 12, 20, 16)
        actions.setSpacing(8)
        self._sel_label = theme.label("케이스를 선택하세요 (Ctrl/Shift로 여러 개)", "caption")
        actions.addWidget(self._sel_label)
        actions.addStretch()
        self._b_owner = _btn("작성자 변경", icon="user")
        self._b_owner.clicked.connect(self._change_owner)
        actions.addWidget(self._b_owner)
        self._b_delete = _btn("선택 삭제", "danger-ghost", "trash")
        self._b_delete.clicked.connect(self._delete)
        actions.addWidget(self._b_delete)
        c_ly.addLayout(actions)
        ly.addWidget(card, 1)
        self._update_buttons()

    def refresh(self) -> None:
        ok, cases = _run(self, "케이스 목록", api_client.list_cases)
        if ok:
            self._cases = cases
            self._fill()
        ok, st = _run(self, "서버 상태", api_client.admin_status)
        if ok:
            self._set_tile("cases", f"{st['cases']:,}건", f"사용자 {st['activeUsers']}/{st['users']}명")
            self._set_tile("xray", f"{st['xrayCount']:,}장", _fmt_bytes(st["xrayBytes"]))
            self._set_tile("db", _fmt_bytes(st["dbBytes"]), "PostgreSQL")
            pct = st["diskFree"] / st["diskTotal"] * 100 if st["diskTotal"] else 0
            self._set_tile("disk", _fmt_bytes(st["diskFree"]), f"전체 {_fmt_bytes(st['diskTotal'])} 중 {pct:.0f}%")
            lb = api_client.parse_time(st.get("lastBackup"))
            self._set_tile("backup", _fmt_dt(lb) if lb else "아직 없음",
                           "매일 03:30 자동 · Vultr 자동 백업 별도")

    def _set_tile(self, key: str, value: str, hint: str) -> None:
        self._tiles[key][0].setText(value)
        self._tiles[key][1].setText(hint)

    def _fill(self) -> None:
        q = self._search.text().strip().lower()
        rows = [c for c in self._cases if not q or any(
            q in (c.get(f) or "").lower() for f in ("patientName", "patientRegNo", "doctorName"))]
        self._table.setRowCount(len(rows))
        for r, c in enumerate(rows):
            self._table.setItem(r, 0, _item(_fmt_dt(c.get("createdAt")), c["id"], color=theme.TEXT_2))
            self._table.setItem(r, 1, _item(c.get("patientName") or "", bold=True))
            self._table.setItem(r, 2, _item(c.get("patientRegNo") or "", color=theme.TEXT_2))
            self._table.setItem(r, 3, _item(c.get("patientBirth") or "", color=theme.TEXT_2))
            self._table.setItem(r, 4, _item(c.get("doctorName") or ""))
            self._table.setItem(r, 5, _item("있음" if c.get("hasXray") else "-",
                                            color=theme.SUCCESS if c.get("hasXray") else theme.MUTED))
            self._table.setItem(r, 6, _item("발송" if c.get("alimtalkSent") else "-",
                                            color=theme.SUCCESS if c.get("alimtalkSent") else theme.MUTED))
        self._count.setText(f"{len(rows)}건" + (f" / 전체 {len(self._cases)}건" if q else ""))
        self._update_buttons()

    def _selected_ids(self) -> list[str]:
        return [self._table.item(i.row(), 0).data(Qt.ItemDataRole.UserRole)
                for i in self._table.selectionModel().selectedRows()]

    def _update_buttons(self) -> None:
        n = len(self._selected_ids())
        self._b_owner.setEnabled(n > 0)
        self._b_delete.setEnabled(n > 0)
        self._sel_label.setText(f"{n}건 선택" if n else "케이스를 선택하세요 (Ctrl/Shift로 여러 개)")

    def _change_owner(self) -> None:
        ids = self._selected_ids()
        ok, users = _run(self, "작성자 변경", api_client.admin_list_users)
        if not ok:
            return
        users = [u for u in users if u["isActive"]]
        labels = [f"{u['name']} ({u['username']})" for u in users]
        choice, ok = QInputDialog.getItem(
            self, "작성자 변경",
            f"선택한 케이스 {len(ids)}건의 작성자를 누구로 바꿀까요?\n새 작성자만 해당 케이스를 수정할 수 있게 됩니다.",
            labels, 0, False,
        )
        if not ok:
            return
        to = users[labels.index(choice)]
        done = 0
        for cid in ids:
            ok, _ = _run(self, "작성자 변경", api_client.admin_change_owner, cid, to["id"])
            if not ok:
                break
            done += 1
        msgbox.information(self, "작성자 변경", f"{done}건의 작성자를 {to['name']} 선생님으로 바꿨습니다.")
        self.refresh()
        self.changed.emit()

    def _delete(self) -> None:
        ids = self._selected_ids()
        names = [c.get("patientName", "") for c in self._cases if c["id"] in ids]
        preview = ", ".join(names[:5]) + (f" 외 {len(names) - 5}건" if len(names) > 5 else "")
        if msgbox.question(
            self, "케이스 삭제",
            f"선택한 {len(ids)}건을 삭제할까요?\n{preview}\n\nX-ray 이미지도 함께 삭제되며 되돌릴 수 없습니다.",
        ) != QMessageBox.StandardButton.Yes:
            return
        done = 0
        for cid in ids:
            ok, _ = _run(self, "케이스 삭제", api_client.admin_delete_case, cid)
            if not ok:
                break
            done += 1
        msgbox.information(self, "케이스 삭제", f"{done}건을 삭제했습니다.")
        self.refresh()
        self.changed.emit()

    def _export(self) -> None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
        path, _ = QFileDialog.getSaveFileName(
            self, "엑셀(CSV)로 저장", f"무지외반증_케이스_{stamp}.csv", "CSV 파일 (*.csv)",
        )
        if not path:
            return
        ok, data = _run(self, "내보내기", api_client.admin_export_csv)
        if not ok:
            return
        try:
            with open(path, "wb") as f:
                f.write(data)
        except OSError as e:
            msgbox.critical(self, "저장 실패", f"파일을 저장하지 못했습니다:\n{e}")
            return
        msgbox.information(
            self, "내보내기 완료",
            f"저장했습니다:\n{path}\n\n환자 개인정보가 들어 있으니 보관과 전달에 주의하세요.",
        )


class AdminWidget(QWidget):
    """관리자 화면: 상단 토글로 사용자 관리 / 데이터 관리 전환."""

    data_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        ly = QVBoxLayout(self)
        ly.setContentsMargins(32, 28, 32, 24)
        ly.setSpacing(18)

        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(4)
        titles.addWidget(theme.label("관리자", "title"))
        titles.addWidget(theme.label("의료진 계정과 전체 케이스 데이터를 관리합니다.", "subtitle"))
        head.addLayout(titles)
        head.addStretch()

        seg = QFrame()
        seg.setObjectName("segment")
        s_ly = QHBoxLayout(seg)
        s_ly.setContentsMargins(3, 3, 3, 3)
        s_ly.setSpacing(2)
        group = QButtonGroup(self)
        self._tab_users = QRadioButton("사용자 관리")
        self._tab_data = QRadioButton("데이터 관리")
        for i, r in enumerate((self._tab_users, self._tab_data)):
            r.setProperty("segment", True)
            r.setCursor(Qt.CursorShape.PointingHandCursor)
            r.setMinimumWidth(110)
            group.addButton(r, i)
            s_ly.addWidget(r)
        self._tab_users.setChecked(True)
        head.addWidget(seg, 0, Qt.AlignmentFlag.AlignVCenter)
        head.addSpacing(8)
        refresh = _btn("  새로고침", "secondary", "refresh")
        refresh.clicked.connect(self.refresh)
        head.addWidget(refresh, 0, Qt.AlignmentFlag.AlignVCenter)
        ly.addLayout(head)

        self._stack = QStackedWidget()
        self._users = UsersPage()
        self._data = DataPage()
        self._users.changed.connect(self.data_changed.emit)
        self._data.changed.connect(self.data_changed.emit)
        self._stack.addWidget(self._users)
        self._stack.addWidget(self._data)
        group.idClicked.connect(self._switch)
        ly.addWidget(self._stack, 1)

    def _switch(self, idx: int) -> None:
        self._stack.setCurrentIndex(idx)
        self.refresh()

    def refresh(self) -> None:
        (self._users if self._stack.currentIndex() == 0 else self._data).refresh()
