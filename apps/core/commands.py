"""Helpers shared by the setup commands (manage.py seed_* and setup_trac)."""

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.permissions import can_propose

USER_HELP = "Username of the Tech Risk user who proposes the drafts. They must have signed in to TRAC once."


def tech_risk_user(username):
    """The Tech Risk user who will propose seeded drafts, or a clear error."""
    try:
        user = get_user_model().objects.get(username=username)
    except get_user_model().DoesNotExist:
        raise CommandError(f"No user named {username}. Sign in to TRAC once with that account, then run this again.")
    if not can_propose(user):
        raise CommandError(f"{username} can't propose changes. Use a Tech Risk user.")
    return user


def run_parts(command, parts):
    """Run several management commands in turn for a wrapper command (check_content and friends).

    `parts` is a list of (heading, command name, options). Each gets a heading; a part that fails is
    reported and the others still run. Raises CommandError at the end if any failed.
    """
    results = []
    for heading, name, options in parts:
        command.stdout.write(command.style.MIGRATE_HEADING(heading))
        try:
            call_command(name, stdout=command.stdout, stderr=command.stderr, **options)
            results.append((heading, True))
        except CommandError as error:
            command.stdout.write(command.style.ERROR(str(error)))
            results.append((heading, False))
        except SystemExit:  # check_controls ends this way after listing its problems
            results.append((heading, False))
        command.stdout.write("")
    command.stdout.write(command.style.MIGRATE_HEADING("Summary"))
    for heading, ok in results:
        command.stdout.write(f"  {heading}: {'OK' if ok else 'PROBLEMS (see above)'}")
    failed = [heading for heading, ok in results if not ok]
    if failed:
        raise CommandError(f"Needs attention: {', '.join(failed)}.")
    command.stdout.write(command.style.SUCCESS("All done."))
