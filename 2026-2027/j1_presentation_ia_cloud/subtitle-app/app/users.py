"""Account management from the command line: `python -m app.users <command>`.

    python -m app.users create alice            # asks for the password
    python -m app.users create root --admin
    python -m app.users passwd alice            # new password; ends the account's sessions
    python -m app.users disable alice | enable alice
    python -m app.users list

In Docker: `docker compose exec api python -m app.users create root --admin`.
"""

import argparse
import getpass
import sys

from sqlalchemy import delete, select

from app import auth
from app.config import get_settings
from app.db import init_db, session_scope
from app.models import AuthSession, User, utcnow


def _ask_password() -> str:
    password = getpass.getpass("Mot de passe : ")
    if getpass.getpass("Confirmation : ") != password:
        raise SystemExit("Les deux mots de passe diffèrent.")
    return password


def _find(session, username: str) -> User:
    user = session.scalar(select(User).where(User.username == auth.normalize_username(username)))
    if user is None:
        raise SystemExit(f"Compte introuvable : {username}")
    return user


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.users", description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="créer un compte")
    create.add_argument("username")
    create.add_argument("--admin", action="store_true", help="compte administrateur")
    for name in ("passwd", "disable", "enable"):
        commands.add_parser(name).add_argument("username")
    commands.add_parser("list", help="lister les comptes")
    args = parser.parse_args(argv)

    init_db(get_settings().database_url)
    with session_scope() as session:
        if args.command == "list":
            for user in session.scalars(select(User).order_by(User.created_at)):
                state = "désactivé" if user.disabled_at else "actif"
                print(f"{user.username}\t{user.role}\t{state}")
        elif args.command == "create":
            try:
                auth.create_user(
                    session, args.username, _ask_password(),
                    auth.ROLE_ADMIN if args.admin else auth.ROLE_USER,
                )
            except (ValueError, auth.UsernameTaken) as exc:
                raise SystemExit(f"Compte non créé : {exc}") from exc
            print("Compte créé.")
        elif args.command == "passwd":
            user = _find(session, args.username)
            password = _ask_password()
            try:
                auth.validate_password(password)
            except ValueError as exc:
                raise SystemExit(str(exc)) from exc
            user.password_hash = auth.hash_password(password)
            session.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
            print("Mot de passe changé ; les connexions en cours sont terminées.")
        else:
            user = _find(session, args.username)
            if args.command == "disable":
                user.disabled_at = utcnow()
                session.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
            else:
                user.disabled_at = None
            print("Fait.")


if __name__ == "__main__":
    main(sys.argv[1:])
