"""Deliberately backdated GitHub calendar art; Python standard library only."""

import argparse
from collections import Counter
import csv
from datetime import date, datetime, timezone
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
CSV = "github_contribution_pixel_dates_2020_2022.csv"
LOG = "artwork.log"
TARGETS = {2020: ("BRO?", 42, 12), 2021: ("OBSESSED?", 98, 8),
           2022: ("HIRE ME?", 79, 20)}
DOCS = [CSV, "generate.py", "README.md"]
DOC_MESSAGE = "docs: disclose backdated contribution-calendar pixel art"
WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday"]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(*args, env=None, check=True):
    # Disable signing/hooks and automatic maintenance for these local commands.
    # No persistent or global Git configuration is changed.
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=NUL",
         "-c", "gc.auto=0", *args], cwd=ROOT, env=env, check=check,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8")


def read_pixels():
    with (ROOT / CSV).open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    require(len(rows) == 219, f"Expected 219 CSV rows, got {len(rows)}")
    pixels = []
    seen = set()
    for line, row in enumerate(rows, 2):
        day = date.fromisoformat(row["date"])
        year = int(row["year"])
        require(year in TARGETS and day.year == year, f"Row {line}: wrong year")
        message, _, _ = TARGETS[year]
        require(row["message"].upper() == message, f"Row {line}: wrong message")
        require(day not in seen, f"Row {line}: duplicate date {day}")
        seen.add(day)
        column = int(row["week_column_0_based"])
        weekday = int(row["weekday_row_0_based_sunday_first"])
        # Check the supplied coordinates; never use these calculations to move art.
        jan1 = date(year, 1, 1)
        expected_column = ((day - jan1).days + (jan1.weekday() + 1) % 7) // 7
        require(0 <= column < 53 and column == expected_column,
                f"Row {line}: incorrect week column")
        require(0 <= weekday < 7 and weekday == (day.weekday() + 1) % 7,
                f"Row {line}: incorrect weekday row")
        require(row["weekday"] == WEEKDAYS[weekday], f"Row {line}: weekday mismatch")
        position = int(row["character_position_1_based"])
        require(1 <= position <= len(message) and
                row["character"] == message[position - 1] and row["character"] != " ",
                f"Row {line}: character mismatch")
        pixels.append((day, column, weekday))
    counts = Counter(day.year for day, _, _ in pixels)
    for year, (_, expected, _) in TARGETS.items():
        require(counts[year] == expected, f"{year}: incorrect number of pixel dates")
    return sorted(pixels)


def preview(pixels):
    for year, (message, count, commits) in TARGETS.items():
        grid = [["." for _ in range(53)] for _ in range(7)]
        for day, column, weekday in pixels:
            if day.year == year:
                grid[weekday][column] = "#"
        print(f"\n{year}: {message} | {count} dates x {commits} = {count * commits} commits")
        for label, row in zip(WEEKDAYS, grid):
            print(f"{label[:3]} {''.join(row)}")
    print("\nCSV validation PASS: 219 unique dates; all year/week/day positions match.")
    print("Planned generated commits: 2868. ASCII grids: 53 columns x 7 rows.", flush=True)


def identity():
    name = git("config", "--get", "user.name").stdout.strip()
    email = git("config", "--get", "user.email").stdout.strip()
    require(name and email, "Configure a local Git author name and email first")
    print(f"Configured Git author: {name} <{email}>", flush=True)
    return name, email


def records(pixels):
    for day, _, _ in pixels:
        count = TARGETS[day.year][2]
        for index in range(1, count + 1):
            stamp = f"{day.isoformat()}T12:00:{index:02d}+00:00"
            message = f"graffiti: {day.isoformat()} pixel {index:02d}/{count}"
            record = f"{day.isoformat()} {index:02d}/{count}\n"
            yield stamp, message, record


def verify(pixels):
    expected = list(records(pixels))
    history = git("log", "--reverse", "--format=%aI|%cI|%s", "--numstat").stdout
    commits = []
    for line in history.splitlines():
        if "|" in line:
            author, committer, subject = line.split("|", 2)
            author = author.replace("Z", "+00:00")
            committer = committer.replace("Z", "+00:00")
            commits.append((author, committer, subject, []))
        elif line.strip():
            commits[-1][3].append(line)
    require(len(commits) == 2869, f"Expected 2869 total commits, got {len(commits)}")
    counts = Counter()
    for actual, (stamp, message, _) in zip(commits[:-1], expected):
        author, committer, subject, changes = actual
        require((author, committer, subject) == (stamp, stamp, message),
                f"History deviation: {subject}")
        require(changes == [f"1\t0\t{LOG}"], f"Unexpected artwork change: {subject}")
        counts[author[:10]] += 1
    targets = {day.isoformat(): TARGETS[day.year][2] for day, _, _ in pixels}
    require(dict(counts) == targets, "Date counts differ from the CSV targets")
    author, committer, subject, changes = commits[-1]
    require(subject == DOC_MESSAGE and author == committer and
            datetime.fromisoformat(author).year > 2022,
            "Unexpected documentation commit or historical date")
    require(sorted(change.split("\t", 2)[2] for change in changes) == sorted(DOCS),
            "Documentation commit contains unexpected files")
    require((ROOT / LOG).read_text(encoding="utf-8") ==
            "".join(record for _, _, record in expected), "Artwork log differs from plan")
    require(not git("status", "--porcelain").stdout.strip(), "Working tree is not clean")
    for year, (_, count, per_day) in TARGETS.items():
        print(f"{year}: PASS - {count} dates, exactly {per_day} commits each ({count * per_day})")
    print("History verification PASS: 2868 historical + 1 modern documentation = 2869 commits.")
    print("Deviations: 0. Unintended historical dates: 0. All artwork changes: +1/-0 artwork.log.")


def generate(pixels, confirmed_email):
    name, email = identity()
    require(confirmed_email == email,
            "Confirm this email belongs to your GitHub account, then supply --confirmed-email EMAIL")
    require(git("rev-parse", "--show-toplevel").stdout.strip().replace("\\", "/") ==
            ROOT.as_posix(), "Must run in this dedicated repository")
    require(git("symbolic-ref", "--short", "HEAD").stdout.strip() == "main", "Branch must be main")
    require(not git("remote").stdout.strip(), "Generation requires a local-only repository")
    require(git("rev-parse", "--verify", "HEAD", check=False).returncode != 0,
            "Refusing to generate twice: repository already has history")
    require(not (ROOT / LOG).exists(), "Refusing to overwrite an existing artwork log")
    status = git("status", "--porcelain", "--untracked-files=all").stdout.splitlines()
    require(sorted(status) == sorted(f"?? {file}" for file in DOCS),
            "Expected only the three untracked source files; index must be empty")
    git_dir = Path(git("rev-parse", "--absolute-git-dir").stdout.strip())
    # Exclusive creation guards concurrent runs and persists after an interrupted run.
    with (git_dir / "graffiti-generation.lock").open("x", encoding="utf-8") as lock:
        lock.write("Generation started. Do not delete to retry in this repository.\n")
    env = os.environ.copy()
    for key in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        env[key] = name
    for key in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        env[key] = email
    total = 0
    for stamp, message, record in records(pixels):
        # Close after each append: Windows may cache size metadata on an open handle.
        with (ROOT / LOG).open("x" if total == 0 else "a",
                               encoding="utf-8", newline="\n") as artwork:
            artwork.write(record)
        env["GIT_AUTHOR_DATE"] = stamp
        env["GIT_COMMITTER_DATE"] = stamp
        if total == 0:
            git("add", "--", LOG, env=env)
        git("commit", "--quiet", "--only", "-m", message, "--", LOG, env=env)
        total += 1
        if total % 100 == 0:
            print(f"Generated {total}/2868 historical commits ({stamp[:10]})", flush=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = now
    git("add", "--", *DOCS, env=env)
    git("commit", "--quiet", "-m", DOC_MESSAGE, env=env)
    verify(pixels)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--generate", action="store_true")
    mode.add_argument("--verify", action="store_true")
    parser.add_argument("--confirmed-email", help="Email you confirmed belongs to your GitHub account")
    args = parser.parse_args()
    pixels = read_pixels()
    preview(pixels)  # Always show validated source coordinates before any generation.
    if args.generate:
        generate(pixels, args.confirmed_email)
    elif args.verify:
        verify(pixels)
    else:
        identity()
        print("Dry-run PASS: no files or Git history changed.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError):
            print(error.stderr.strip(), file=sys.stderr)
        sys.exit(1)
