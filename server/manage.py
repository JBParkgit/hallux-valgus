"""Admin commands for the server (run on the Vultr box).

    python manage.py init-db
    python manage.py add-doctor <username> <이름>          # prompts for password
    python manage.py reset-password <username>
    python manage.py set-active <username> on|off
    python manage.py set-admin <username> on|off        # 관리자 지정/해제
    python manage.py list-doctors
"""

from __future__ import annotations

import getpass
import sys

from hv_server import db, security


def _ask_password() -> str:
    while True:
        pw = getpass.getpass("비밀번호: ")
        if not pw:
            print("비밀번호를 입력해 주세요.")
            continue
        if pw != getpass.getpass("비밀번호 확인: "):
            print("일치하지 않습니다.")
            continue
        return pw


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    cmd, args = argv[0], argv[1:]

    if cmd == "init-db":
        db.init_schema()
        print("스키마 준비 완료")
    elif cmd == "add-doctor" and len(args) >= 2:
        username, name = args[0], " ".join(args[1:])
        pw = _ask_password()
        with db.cursor() as cur:
            cur.execute(
                'INSERT INTO "Doctor" (id, username, "passwordHash", name) VALUES (%s, %s, %s, %s)',
                (security.new_id(), username, security.hash_password(pw), name),
            )
        print(f"계정 생성: {username} ({name})")
    elif cmd == "reset-password" and len(args) == 1:
        pw = _ask_password()
        with db.cursor() as cur:
            cur.execute(
                'UPDATE "Doctor" SET "passwordHash" = %s WHERE username = %s',
                (security.hash_password(pw), args[0]),
            )
            found = cur.rowcount > 0
            # log out everywhere
            cur.execute(
                'DELETE FROM "Session" WHERE "doctorId" = (SELECT id FROM "Doctor" WHERE username = %s)',
                (args[0],),
            )
        print("변경 완료 (모든 PC에서 로그아웃됨)" if found else "계정 없음")
    elif cmd == "set-active" and len(args) == 2 and args[1] in ("on", "off"):
        with db.cursor() as cur:
            cur.execute(
                'UPDATE "Doctor" SET "isActive" = %s WHERE username = %s',
                (args[1] == "on", args[0]),
            )
            if args[1] == "off":
                cur.execute(
                    'DELETE FROM "Session" WHERE "doctorId" = (SELECT id FROM "Doctor" WHERE username = %s)',
                    (args[0],),
                )
        print("완료")
    elif cmd == "set-admin" and len(args) == 2 and args[1] in ("on", "off"):
        with db.cursor() as cur:
            cur.execute('UPDATE "Doctor" SET "isAdmin" = %s WHERE username = %s', (args[1] == "on", args[0]))
            if cur.rowcount == 0:
                print("계정 없음")
                return 1
        print("완료")
    elif cmd == "list-doctors":
        with db.cursor() as cur:
            cur.execute('SELECT username, name, "isActive", "isAdmin", "createdAt" FROM "Doctor" ORDER BY "createdAt"')
            for r in cur.fetchall():
                state = "사용" if r["isActive"] else "중지"
                role = "관리자" if r["isAdmin"] else ""
                print(f'{r["username"]:<16} {r["name"]:<10} {state}  {r["createdAt"]:%Y-%m-%d}  {role}')
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
