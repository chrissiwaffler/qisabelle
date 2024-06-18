import gzip
import json
import os
from multiprocessing import Process, Queue
from pathlib import Path
from queue import Empty as QueueEmpty

from .extractions import ExtractedTheory
from .session import QIsabelleSession
from .utils import read_env_dict

ROOT_DIR = Path(__file__).parent.parent
EXTRACTIONS_DIR = ROOT_DIR / "extractions"

ENVIRONMENT = read_env_dict(ROOT_DIR / ".env") | os.environ
AFP_DIR = Path(ENVIRONMENT["AFP_DIR"])
ISABELLE_DIR = Path(ENVIRONMENT["ISABELLE_DIR"])
if not AFP_DIR.is_absolute():
    AFP_DIR = (ROOT_DIR / AFP_DIR).resolve()
if not ISABELLE_DIR.is_absolute():
    ISABELLE_DIR = (ROOT_DIR / ISABELLE_DIR).resolve()


def extract_session(session_name: str, thy_files: list[Path], port: int) -> None:
    """
    Extract given theories within a given session.

    Already extracted sessions and theory files are skipped.
    """
    session_dir = AFP_DIR / "thys" / session_name
    if session_name == "HOL":
        session_dir = ISABELLE_DIR / "src" / "HOL"

    if (EXTRACTIONS_DIR / session_name / "done").exists():
        print(f"[{port}] Skipping {session_name}, already done.")
        return
    (EXTRACTIONS_DIR / session_name).mkdir(exist_ok=True, parents=True)

    try:
        with QIsabelleSession(
            port=port,
            session_name=session_name,
            session_roots=[Path("/afp/thys")],
            per_transition_timeout=60.0,
        ) as qisabelle:
            for thy_file in thy_files:
                thy_id = str(thy_file.with_suffix("").relative_to(session_dir)).replace("/", ".")
                extract_theory(qisabelle, session_name, thy_file, thy_id)
    except Exception as e:
        print(f"[{port}] Error extracting {session_name}: {e}")
        (EXTRACTIONS_DIR / session_name / "error").write_text(repr(e))

    (EXTRACTIONS_DIR / session_name / "done").write_text("")


def extract_theory(
    qisabelle: QIsabelleSession, session_name: str, thy_file: Path, thy_id: str
) -> None:
    print(f"[{qisabelle.port}] Loading {thy_file}")
    p = EXTRACTIONS_DIR / session_name / (thy_id + ".json.gz")
    if p.exists():
        print(f"[{qisabelle.port}] Skipping {thy_file}, already done.")
        return

    if session_name == "HOL":
        inner_thy_file = Path("/home/isabelle/Isabelle") / thy_file.relative_to(ISABELLE_DIR)
    else:
        inner_thy_file = Path("/afp") / thy_file.relative_to(AFP_DIR)

    try:
        extractions: ExtractedTheory = qisabelle.extract_theory(inner_thy_file)

        with gzip.open(p, "wt", encoding="ascii") as f:
            json.dump(extractions, f)
    except Exception as e:
        print(f"[{qisabelle.port}] Error extracting {thy_file}: {e}")
        p.with_suffix(".error").write_text(repr(e))


def main(ports: list[int]) -> None:
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
        # TODO for HOL this doesn't work.

    q: "Queue[tuple[str, list[Path]]]" = Queue()
    workers = [Process(target=worker, args=(q, port)) for port in ports]
    for w in workers:
        w.start()
    for session_name, thy_files in sessions.items():
        q.put((session_name, thy_files))
    for w in workers:
        q.put(("", []))
    q.close()
    for w in workers:
        w.join()


def worker(q: "Queue[tuple[str, list[Path]]]", port: int) -> None:
    try:
        while True:
            session_name, thy_files = q.get(block=True)
            if not session_name:
                print(f"[{port}] Finishing.")
            extract_session(session_name, thy_files, port)
    except QueueEmpty:
        print(f"[{port}] Queue empty.")
        return


if __name__ == "__main__":
    main(ports=[17000 + i for i in range(4)])
