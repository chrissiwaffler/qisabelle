from typing import TypedDict


class Theory(TypedDict):
    path: str  # Path to this .thy file (in container).
    sessionName: str  # Name of the Isabelle session that we ran this theory in.
    name: str  # Name of the theory (from its header).
    imports: list[str]  # List of theory names or paths to import (from its header).
    importNames: list[str]  # List of theory names (resolved).


class Position(TypedDict):
    # Offsets count Isabelle symbols (not UTF8 or UTF16) in the whole text (not just the current line).
    line: int  # Line number of the transition (starts from 1).
    offset: int  # Beginning offset (inclusive).
    endOffset: int  # End offset (exclusive).


class Transition(TypedDict):
    name: str  # E.g. "theory", "section", "lemma", "by", "using", "definition",
    # 'locale", "record", "end", "<ignored>", "<malformed>".
    text: str  # Text (code) of the transition.
    position: Position


class State(TypedDict):
    mode: str  # One of: Toplevel, Theory (global), LocalTheory, Proof, SkippedProof
    proofState: str  # Description of the current proof state, starting like "proof (prove)\ngoal (1 subgoal):\n 1. ".
    localTheory: str  # Description like "theory Foo" or "locale foo", or "class foo = ...".
    proofLevel: int  # Number of opened proof blocks, ML function `Toplevel.level`), zero when outside of proofs.
    # For Skipped_Proof, this is instead the depth (plus one).


class Extraction(TypedDict):
    transition: Transition
    state: State


class ExtractedTheory(TypedDict):
    theory: Theory
    extractions: list[Extraction]
