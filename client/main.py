import os
import pprint
import textwrap
import time
from collections import defaultdict
from pathlib import Path

from .model import DummyHammerModel, Model
from .session import QIsabelleSession, get_exception_kind
from .test_cases import TestCase, load_quick_test_cases
from .utils import read_env_dict


def main() -> None:
    test_new_theory()
    # test_going_into_theory()
    # test_extract_session()
    # test_pisa()


def test_new_theory() -> None:
    with QIsabelleSession(session_name="HOL", session_roots=[]) as session:
        # Initialize a new theory with imports from HOL, store as "state0".
        session.new_theory(
            theory_name="Test",
            new_state_name="state0",
            imports=["Complex_Main", "HOL-Computational_Algebra.Primes"],
            only_import_from_session_heap=False,
        )
        print(session.describe_state("state0"))

        # Execute a lemma statement, store as "state1".
        lemma = 'lemma foo: "prime p \\<Longrightarrow> p > (1::nat)"'
        is_proof_done, proof_goals = session.execute("state0", lemma, "state1")
        assert not is_proof_done
        print(indent(proof_goals))  # "proof (prove) goal (1 subgoal):"...

        # Execute a proof and check that it proved the lemma.
        proof = "using prime_gt_1_nat by simp"
        is_proof_done, proof_goals = session.execute("state1", proof, "state2")
        assert is_proof_done and not proof_goals

        # Find an alternative proof with Sledgehammer.
        proof = session.hammer("state1", deleted_facts=["prime_gt_1_nat"])
        print(indent(proof))  # "by (simp add: prime_nat_iff)"
        is_proof_done, proof_goals = session.execute("state1", proof, "state3")
        assert is_proof_done and not proof_goals


def test_going_into_theory() -> None:
    thy_file = Path("/home/isabelle/Isabelle/src/HOL/Examples/Seq.thy")
    with QIsabelleSession(theory_path=thy_file) as session:
        # Load all the theory until a given lemma statement, inclusive, store as "state0".
        lemma = 'lemma reverse_reverse: "reverse (reverse xs) = xs"'
        is_proof_done, proof_goals = session.load_theory(
            thy_file, lemma, inclusive=True, new_state_name="state0"
        )
        print(session.describe_state("state0"))
        assert not is_proof_done
        assert proof_goals.startswith("proof (prove)\ngoal (1 subgoal):\n")

        proof = "by (induct xs) (simp_all add: reverse_conc)"
        is_proof_done, proof_goals = session.execute("state0", proof, "state1")
        assert is_proof_done and not proof_goals


def test_extract_session() -> None:
    """Show the JSONs extracted from an example session's theories."""
    ROOT_DIR = Path(__file__).parent.parent
    ENVIRONMENT = read_env_dict(ROOT_DIR / ".env") | os.environ
    AFP_DIR = Path(ENVIRONMENT["AFP_DIR"])
    if not AFP_DIR.is_absolute():
        AFP_DIR = ROOT_DIR / AFP_DIR

    session_name = "BNF_Operations"
    session_dir = AFP_DIR / "thys" / session_name
    assert (session_dir / "ROOT").exists()
    with QIsabelleSession(session_name=session_name, session_roots=[Path("/afp/thys")]) as session:
        for thy_file in session_dir.glob("*.thy"):
            print(f"Loading {thy_file}")
            pprint.pp(session.extract_theory(Path("/afp") / thy_file.relative_to(AFP_DIR)))


def test_pisa() -> None:
    """Run the 600 'quick' tests from PISA on a model that just uses Sledgehammer at every step.

    This takes hours on a powerful server.

    Currently on default settings the results for this model are roughly:
    * success: 179
    * timeout-soft: 118, timeout-mid: 1, timeout-hard: 283 (hammer timeouts)
    * execution-timeout: 6 (proof, or theory up to lemma statement, takes too long to execute)
    * failed-proof: 1 (proof given by hammer fails)
    * not_found: 10, no_such_file: 1  (test extracted from a different version of AFP than we have).

    With larger hammer timeouts (60s) we can get to ~203 successes, so this varies with computing power.
    """
    ROOT_DIR = Path(__file__).parent.parent
    ENVIRONMENT = read_env_dict(ROOT_DIR / ".env") | os.environ
    AFP_DIR = Path(ENVIRONMENT["AFP_DIR"])
    if not AFP_DIR.is_absolute():
        AFP_DIR = ROOT_DIR / AFP_DIR

    test_dir = ROOT_DIR / "test_theorems" / "PISA"
    print("Loading tests from", test_dir)
    tests = load_quick_test_cases(test_dir)
    print(f"Loaded {len(tests)} tests.")

    # Warn about theory files not in tests but not in our AFP version.
    for test in tests:
        thy_file = AFP_DIR / "thys" / test.thy_file
        if not thy_file.exists():
            print(f"Warning ({test.name}): no such theory file: {thy_file}")

    evaluate_model(DummyHammerModel(), tests)


def evaluate_model(model: Model, tests: list[TestCase]) -> None:
    summary: dict[str, int] = defaultdict(int)
    for i, test_case in enumerate(tests):
        print(header(f"Test case {test_case.name}, thy file: {test_case.thy_file}"))
        print(header("Lemma statement"))
        print(indent(test_case.lemma_statement))

        theory_path = Path("/afp/thys") / test_case.thy_file
        try:
            print(header("Server init"))
            with QIsabelleSession(theory_path=theory_path) as session:
                r = run_model_greedily(model, theory_path, test_case.lemma_statement, session)
            result = "success" if r else "failure"
        except Exception as e:
            print(header("Exception"))
            print(indent(str(e)))
            result = get_exception_kind(e)

        summary[result] += 1
        print(header(result, "$"))
        print(f"Did {i + 1} / {len(tests)} tests so far:", dict(summary.items()))
        print("\n\n\n")
    print(f"Finished evaluation. Results:\n    {dict(summary.items())} / {len(tests)}")


def run_model_greedily(
    model: Model,
    theory_path: Path,
    lemma_statement: str,
    session: QIsabelleSession,
    max_proof_search_time: float = 500.0,
) -> bool:
    """
    Run a model greedily, until it finds a proof, runs out of time, or fails to change the state.

    Args:
    - model
    - theory_path: path to .thy file in server.
    - lemma_statement: statement of lemma to prove (should appear in the theory file).
    - session: QIsabelleSession initialized with a session containing the theory (or all its imports).
    - max_proof_search_time: float seconds, maximum time to search for a proof.
    """
    print(" Load theory ".center(100, "%"))
    state_name = "s"
    prev_proof_step = lemma_statement
    is_proof_done, proof_goals = session.load_theory(theory_path, lemma_statement, True, state_name)
    assert not is_proof_done

    end_time = time.time() + max_proof_search_time
    while time.time() < end_time:
        print(header("Proof state"))
        print(indent(proof_goals))

        generated_steps = model(prev_proof_step, proof_goals)
        if not generated_steps:
            return False
        proof_step, subscore = generated_steps[0]
        print(header(f"Model gave (with {subscore=})"))
        print(indent(proof_step))
        new_state_name = f"{state_name}.0"

        if proof_step.strip() == "normalhammer":
            proof_step = session.hammer(state_name)
            print(header("Hammer gave"))
            print(indent(proof_step))
        is_proof_done, new_proof_state = session.execute(state_name, proof_step, new_state_name)

        if new_proof_state == proof_goals:
            print("Proof state unchanged :(")
            return False

        if is_proof_done:
            return True
        prev_proof_step = proof_step
        state_name = new_state_name

    return False


def indent(text: str, indentation: str = "\t") -> str:
    """Indend text with tabs, strip the final newline."""
    return textwrap.indent(text.strip(), indentation)


def header(title: str, fill_char: str = "%") -> str:
    """Center a string in % chars."""
    return (" " + title + " ").center(100, fill_char)


if __name__ == "__main__":
    main()
