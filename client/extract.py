import gzip
import json
import os
from pathlib import Path

from .session import QIsabelleSession
from .utils import read_env_dict

ROOT_DIR = Path(__file__).parent.parent
EXTRACTIONS_DIR = ROOT_DIR / "extractions"


def main() -> None:
    EXTRACTIONS_DIR.mkdir(exist_ok=True)

    ENVIRONMENT = read_env_dict(ROOT_DIR / ".env") | os.environ
    AFP_DIR = Path(ENVIRONMENT["AFP_DIR"])
    ISABELLE_DIR = Path(ENVIRONMENT["ISABELLE_DIR"])
    if not AFP_DIR.is_absolute():
        AFP_DIR = (ROOT_DIR / AFP_DIR).resolve()
    if not ISABELLE_DIR.is_absolute():
        ISABELLE_DIR = (ROOT_DIR / ISABELLE_DIR).resolve()

    root_dirs = [
        AFP_DIR / "thys" / r for r in (AFP_DIR / "thys" / "ROOTS").read_text().splitlines()
    ]
    # root_dirs = [ISABELLE_DIR / "src" / "HOL"] + root_dirs

    sessions = dict[str, list[Path]]()  # session_name -> list of theory files.
    for root_dir in sorted(root_dirs):
        # We'll assume the root name is a session name and that all .thy files belong in that session.
        # This is mostly true, though technically the ROOT file can list many sessions with arbitrary names,
        # and those session can include theory files from wherever, and transitive includes are not explicitly written.
        # So you'd need to parse ROOT files and theory files and make a graph of all imports and so on.
        sessions[root_dir.name] = sorted(root_dir.glob("**/*.thy"))

    for session_name, thy_files in sessions.items():
        session_dir = AFP_DIR / "thys" / session_name
        if session_name == "HOL":
            session_dir = ISABELLE_DIR / "src" / "HOL"
        assert (session_dir / "ROOT").exists(), f"ROOT file not found in: {session_dir}"

        (EXTRACTIONS_DIR / session_name).mkdir(exist_ok=True)

        if (EXTRACTIONS_DIR / session_name / "done").exists():
            print(f"Skipping {session_name}, already done.")
            continue

        with QIsabelleSession(
            session_name=session_name, session_roots=[Path("/afp/thys")]
        ) as session:
            for thy_file in thy_files:
                print(f"Loading {thy_file}")

                thy_id = str(thy_file.with_suffix("").relative_to(session_dir)).replace("/", ".")
                p = EXTRACTIONS_DIR / session_name / (thy_id + ".json.gz")
                if p.exists():
                    print(f"Skipping {thy_file}, already done.")
                    continue

                if session_name == "HOL":
                    inner_thy_file = Path("/home/isabelle/Isabelle") / thy_file.relative_to(
                        ISABELLE_DIR
                    )
                else:
                    inner_thy_file = Path("/afp") / thy_file.relative_to(AFP_DIR)

                try:
                    extractions = session.extract_theory(inner_thy_file)

                    with gzip.open(p, "wt", encoding="ascii") as f:
                        json.dump(extractions, f)
                except Exception as e:
                    print(f"Error extracting {thy_file}: {e}")
                    p.with_suffix(".error").write_text(repr(e))

            (EXTRACTIONS_DIR / session_name / "done").write_text("")


if __name__ == "__main__":
    main()
